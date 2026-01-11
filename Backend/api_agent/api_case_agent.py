import json

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_core import type_subscription, RoutedAgent, message_handler, MessageContext

from Backend.api_agent.llm_models.llm_models import json_format_model
from Backend.api_agent.prompt_words.api_agent_prompt import api_structure_case_prompt, fix_agent_prompt


@type_subscription("api_structure_case")
class APITestCaseStructureAgent(RoutedAgent):
    """将非结构的测试用例转化为严格的json格式"""

    def __init__(self):
        super().__init__("apicase_structure_agent")
        json_format_example = """
                {
                    "testcases": [
                        {
                            "title": "...",
                            "description": "...",
                            "api_url": "...",
                            "base_url": "http://127.0.0.1:8003",
                            "project_id": 1,
                            "preconditions": "...",
                            "postconditions": "...",
                            "steps": [
                                {
                                    "step_name": "...",
                                    "http_method": "POST",
                                    "step_index": 1,
                                    "url": "...",
                                    "headers": {},
                                    "body": {},
                                    "expected_status_code": 200,
                                    "assertions": ["这是一个字符串断言", "响应中必须包含'id'字段"]
                                }
                            ]
                        }
                    ]
                }
                """
        self.system_message = api_structure_case_prompt(json_format_example)

    UnstructuredMessage = []

    @message_handler
    async def handle_message(self, message: UnstructuredMessage, ctx: MessageContext) -> None:
        print('*' * 10 + 'apicase_structure_agent' + '*' * 10)
        structure_json_str = ""
        try:
            struction_agent = AssistantAgent(
                name='apicase_structure_agent',
                model_client=json_format_model,
                model_client_stream=False,
                system_message=self.system_message
            )
            task = f"请将下述非结构化测试用例转化为结构化JSON格式：\n\n{message.unstructured_text}"

            stream = struction_agent.run_stream(task=task)

            async for msg in stream:
                if isinstance(msg, TaskResult):
                    structure_json_str = msg.messages[-1].content
                    print(structure_json_str)
                    continue

            # 验证
            out_result = json.loads(structure_json_str)
            print(f"json结构化成功，共{len(out_result['testcases'])}个用例")
            # 发送给下一个智能体

        except json.JSONDecodeError as e:
            # 尝试修复json格式错误
            fix_agent = AssistantAgent(
                name='fix_json_agent',
                model_client=json_format_model,
                model_client_stream=False,
                system_message=fix_agent_prompt(e)
            )
            print("json格式错误，正在尝试修复")
            fix_result = await fix_agent.run(task=f"修复以下内容为正确的json格式:\n\n {structure_json_str}")
            fixed_content = fix_result.messages[-1].content
            try:
                # 再次验证
                json.loads(fixed_content)
                print(f"修复成功，修复过后的结果是{fixed_content}")
                # 发送给下一个智能体


            except json.JSONDecodeError as e:
                print(f"修复后的结果不是有效的json{str(e)}")
                raise e
        except Exception as e:
            print(f"API用例结构化出错{e}")
