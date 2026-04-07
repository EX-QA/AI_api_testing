import json
from typing import List, Dict, Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import RoutedAgent, type_subscription, message_handler, MessageContext
from loguru import logger

from Backend.api_agent.llm_models.llm_models import deepseek_llm_model
from Backend.message.messages import SelectedAPICaseInput


class PytestCodeGenerateTeam:
    """
    一个用于生成和审查pytest脚本的智能体团队
    """

    def __init__(self):
        self.generate_system_message = """
        你是一位专业的Python测试代码生成专家。你的首要且最重要的任务是智能地处理前置依赖。

        **核心任务 (按优先级)**:
        0. **处理前置依赖 (最高优先级)**: 仔细分析测试用例的 'preconditions' 和 'steps'。如果一个步骤（如“查询商品”）依赖于一个需要预先存在的资源（如“一个有效的商品”），你必须在测试函数的开头，先生成用于创建该资源的代码（例如，POST到/products）。然后，你必须从创建操作的响应中提取出新资源的ID，并在后续的步骤中使用这个ID，而不是使用任何硬编码的ID。
        1. **函数命名**: 必须是 `test_case_[id]_[english_title]` 的格式。`[english_title]` 必须是根据中文标题生成的、只包含字母和下划线的简短英文描述。
        2. **代码范围**: **只生成测试用例函数部分**，不要包含任何`import`语句、工具类、`fixture`或`class`定义。
        3. **URL处理**: 函数体的第一行必须是 `BASE_URL = os.getenv('BASE_URL', '...')`，其中 '...' 是从测试用例数据中获取的 `base_url`。所有请求的URL都必须使用 `f"{BASE_URL}/..."` 的格式来拼接。
        4. **核心逻辑**: 使用`requests`库来发送HTTP请求，并根据测试用例的断言（assertions）编写`assert`语句。
        5. **输出**: 确保生成的代码是完整且语法正确的Python函数。根据审查者的反馈及时修改代码。

        特别强调：每次输出的代码都必须是完整的函数代码，不能只输出修改后的代码片段。
        
        """
        self.review_system_message = """
        你是一位专业的Python代码审查专家。你的任务是审查由另一个AI（代码生成者）生成的代码。

        **核心审查原则**:
        代码生成者的首要任务是智能地处理前置依赖。这意味着它**必须**用动态生成的资源（例如，通过POST请求创建的商品）来替换测试用例中可能存在的硬编码值（如 `url: "/products/1"`）。你的任务是**验证**这个替换过程是否正确，而不是质疑它为何发生。
        **示例**:
        - **错误的行为**: 如果原始测试用例是 `GET /products/1`，而生成者添加了创建商品的步骤并使用了返回的动态ID，你**绝对不能**建议“应该直接测试GET /products/1”。
        - **正确的行为**: 你应该检查生成者是否正确地调用了创建接口，是否正确地提取并使用了返回的ID。

        **审查清单 (按优先级)**:
        0. **前置依赖检查 (最高优先级)**:
            - **检查是否正确处理了依赖**: 如果测试用例的 'preconditions' 或步骤本身暗示需要一个预先存在的资源（如查询特定ID的商品），代码是否包含了创建该资源的步骤？
            - **检查是否正确使用了动态ID**: 代码是否从创建步骤的响应中正确提取了ID，并在后续步骤中使用了这个动态ID，从而替换掉了原始测试用例中可能存在的硬编码ID？
            - **严禁硬编码ID**: 如果生成者没有动态创建资源，反而直接在代码中使用了硬编码的ID（如 `product_id = 1`），这**是必须指出的严重错误**。
        1. **函数命名检查**: 确保函数名符合 `test_case_[id]_[english_title]` 的格式，且不含中文字符。
        2. **代码范围检查**: 确保代码只包含Pytest测试函数，并且没有 `import` 语句。
        3. **URL处理检查**: 必须验证函数第一行是否正确定义了 `BASE_URL`，并且后续的请求URL是否使用了这个变量进行拼接。
        4. **语法和风格**: 严格审查代码的语法正确性，并确保代码风格符合PEP 8。

        **审查输出格式**:
        - 如果发现问题，必须严格按照以下格式提供反馈 (可以有多条):
        ISSUE: [问题描述]
        SUGGESTION: [修复建议]
        - 当代码完全正确时，必须只回复 "APPROVED"。

        **绝对禁止**:
        - **绝对禁止建议删除正确添加的前置依赖代码。** 如果生成者正确地用动态创建的资源替换了硬编码的ID，这是**正确的行为**，不应被标记为ISSUE。
        - **绝对禁止自己生成或重写任何代码块。** 你的唯一职责是提供反馈或批准。
        """
        self.coder_generator = AssistantAgent(
            name='code_generator_agent',
            model_client=deepseek_llm_model,
            model_client_stream=False,
            system_message=self.generate_system_message
        )
        self.coder_reviewer = AssistantAgent(
            name='code_reviewer_agent',
            model_client=deepseek_llm_model,
            model_client_stream=False,
            system_message=self.review_system_message
        )
        self.termination_condition = TextMentionTermination("APPROVED")

        self.team = RoundRobinGroupChat([self.coder_generator, self.coder_reviewer],
                                        termination_condition=self.termination_condition)

    def get_method_name(self, title):
        """得到脚本的函数名"""
        pass

    async def generate_and_review_script(self, test_case: List[Dict[str, Any]]):
        """
        为每个api测试用例独立生成并审查pytest脚本
        :param test_case:
        :return:
        """
        generated_script = []
        for case in test_case:
            case_id = case['id']

            # 未完成内容
            method_title = self.get_method_name(case.get('title'))
            logger.info(f"正在为用例 {case_id} 生成脚本: {method_title}")

            try:
                task = f"""
                **核心指令**:
                1.  仔细分析当前测试用例的 'preconditions'。
                2.  如果需要前置资源，请参考上面的“API上下文信息”，找到用于创建该资源的API。
                3.  在测试函数的开头，生成调用该创建接口的代码，并从其响应中提取出新资源的ID。
                4.  在后续的测试步骤中，必须使用这个动态获取的ID，而不是任何硬编码的ID。
                5.  函数名中的 `[english_title]` 部分请使用: `{method_title}`

                **当前测试用例数据**:
                ```json
                {json.dumps(case, indent=2)}
                ```

                请严格遵循以上指令和你的系统角色设定，生成一个独立的Pytest测试函数。
                """
                code_stream = self.team.run_stream(task=task)
                async for msg in code_stream:
                    if isinstance(msg, TextMessage):
                        if msg.source == 'code_generator_agent':
                            logger.info("code_generator_agent------\n" + msg.content)
                            continue
                        elif msg.source == 'code_reviewer_agent':
                            logger.info("code_reviewer_agent------\n" + msg.content)
                            continue
            except Exception as e:
                logger.error(f"生成脚本失败: {e}")
                continue


@type_subscription(topic_type="pytest_generate_agent")
class PytestGenerateAgent(RoutedAgent):
    """
    根据选定的测试用例生成pytest脚本智能体
    """

    def __init__(self):
        super().__init__("pytest_generate_agent")
        self.code_team = PytestCodeGenerateTeam()

    @message_handler
    async def handle_message(self, message: SelectedAPICaseInput, ctx: MessageContext) -> None:
        logger.info(f"接收到: {len(message.selected_api_case)}条测试用例，开始生成代码")
        try:
            await self.code_team.generate_and_review_script(message.selected_api_case)
        except Exception as e:
            logger.error(f"生成代码失败: {e}")
            return
