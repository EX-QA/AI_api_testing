import asyncio
import json

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage, UserInputRequestedEvent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import type_subscription, RoutedAgent, message_handler, MessageContext, TopicId, \
    SingleThreadedAgentRuntime, DefaultTopicId
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

from Backend.api_agent.llm_models.llm_models import *
from Backend.api_agent.prompt_words.api_agent_prompt import *
from Backend.controller.api_test_case import api_testcase_create_controller
from Backend.message.messages import *
from Backend.schemas.api_case import APITestCaseCreate


@type_subscription(topic_type="api_content_fetcher")
class APIDocsFetcherAgent(RoutedAgent):
    """api文档内容获取智能体"""

    def __init__(self):
        super().__init__("api_content_fetcher_agent")

    @staticmethod
    async def _get_api_content_by_url(url: str, tag: str = None) -> dict:
        """根据接口url和模块获取接口内容"""
        result_dic = {}
        import requests
        if not url.startswith(("http://", "https://")):
            raise ValueError("仅支持http/https url")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                api_dic = response.json()
                url_dic = api_dic.get('paths')
                if tag:
                    for url, details in url_dic.items():
                        for value in details.values():
                            if value['tags'][0] == tag:
                                result_dic.update({url: details})
                    api_dic['paths'] = result_dic
                    return api_dic
                else:
                    return api_dic

            else:
                raise ValueError(f"获取接口内容失败: {response.status_code}")
        except Exception as e:
            print(f"获取接口内容失败: {e}")

    @message_handler
    async def handle_message(self, message: APIDocsInput, ctx: MessageContext) -> None:
        try:
            api_content = {}
            print('*' * 10 + 'api_content_fetcher_agent' + '*' * 10)
            print("开始获取api文档内容")
            if message.api_docs_url:
                api_content = await self._get_api_content_by_url(message.api_docs_url, message.api_docs_tag)
            elif message.uploaded_file:
                # 上传文件暂时没做
                pass
            else:
                raise ValueError("请提供有效的API文档 或 swagger url 地址")

            print(api_content)
            message.api_doc_content = api_content

            # 发送给下一个智能体
            await self.publish_message(message,
                                       topic_id=TopicId(type="api_analyzer", source=self.id.key))
        except Exception as e:
            print(f"获取api文档内容失败: {e}")


@type_subscription(topic_type="api_analyzer")
class APIAnalyzerAgent(RoutedAgent):
    """api文档内容分析智能体"""

    def __init__(self):
        super().__init__("api_analyzer_agent")
        self.system_prompt = api_analyzer_system_prompt()

    async def _analyze_small_api_doc(self, message: APIDocsInput):
        """小型文档单词分析"""
        api_analysis_task_prompt = small_api_analysis_task_prompt(message)
        analyzer_agent = AssistantAgent(
            name='api_analyzer_agent',
            model_client=kimi_model,
            system_message=self.system_prompt,
            model_client_stream=True
        )
        analysis_result = ''
        stream = analyzer_agent.run_stream(task=api_analysis_task_prompt)

        print('正在分析api文档')
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                pass
                continue
            if isinstance(msg, TaskResult):
                analysis_result = msg.messages[-1].content
                continue
        return analysis_result

    async def _analyze_basic_info(self, message: APIDocsInput, info: dict, components: dict):
        pass

    @message_handler
    async def handle_message(self, message: APIDocsInput, ctx: MessageContext) -> None:
        print('*' * 10 + 'api_analyzer_agent' + '*' * 10)
        print('开始分析API文档')
        try:
            api_doc_str = json.dumps(message.api_doc_content, ensure_ascii=False, indent=2)
            api_doc_size = len(api_doc_str)
            print(f"api接口文件数据为{api_doc_size}")

            api_analysis_result = ''
            if api_doc_size < 30000:
                api_analysis_result = await self._analyze_small_api_doc(message)
            else:
                # 大型文档分析，暂未实现
                pass
            print("分析完成，分析结果如下：\n")
            print(api_analysis_result)

            # 发送给下一个智能体
            await self.publish_message(
                APIAnalysisResult(
                    api_docs_url=message.api_docs_url,
                    base_url=message.base_url,
                    uploaded_file=message.uploaded_file,
                    api_doc_supplement=message.api_doc_supplement,
                    test_focus=message.test_focus,
                    api_analysis_result=api_analysis_result
                ),
                topic_id=TopicId(type='api_test_designer', source=self.id.key)
            )
        except Exception as e:
            print(f"分析api文档失败: {e}")


@type_subscription(topic_type='api_test_designer')
class APICaseDesignerAgent(RoutedAgent):
    """api测试用例设计智能体"""

    def __init__(self, user_input_func):
        super().__init__("api_test_designer_agent")
        self.user_input_func = user_input_func
        self.system_prompt = api_case_design_system_prompt()

    @message_handler
    async def handle_message(self, message: APIAnalysisResult, ctx: MessageContext) -> None:
        print('*' * 10 + 'api_test_designer_agent' + '*' * 10)
        print('开始设计API测试用例')
        try:
            task_prompt = f"""
            请根据以下的API分析报告，设计一套API测试用例。\n\n API分析报告如下：\n{message.api_analysis_result}\n\n
            
            并 要严格遵循以下要求:
            {f"设计要求:{message.test_focus}" if message.test_focus else ""}
"""
            self.system_prompt = self.system_prompt.replace("$base_url$", message.base_url)

            designer_agent = AssistantAgent(
                name="designer_agent",
                model_client=deepseek_llm_model,
                system_message=self.system_prompt,
                model_client_stream=True
            )

            user_reviewer_agent = UserProxyAgent(
                name="user_reviewer_agent",
                input_func=self.user_input_func
            )
            termination_en = TextMentionTermination("approve")
            termination_cn = TextMentionTermination("同意")
            team = RoundRobinGroupChat([designer_agent, user_reviewer_agent],
                                       termination_condition=termination_en | termination_cn)
            final_test_case = ''
            update_count = 0
            testcase_modify_memory = ListMemory()

            chat_stream = team.run_stream(task=task_prompt)
            async for msg in chat_stream:
                if isinstance(msg, ModelClientStreamingChunkEvent):
                    pass
                    continue
                if isinstance(msg, TextMessage):
                    await testcase_modify_memory.add(
                        MemoryContent(content=msg.model_dump_json(), mime_type=MemoryMimeType.JSON)
                    )
                    if msg.source == 'user_reviewer_agent' and all(a not in msg.content for a in ['approve', '同意']):
                        update_count += 1
                    if msg.source == 'designer_agent':
                        final_test_case = msg.content.strip()
                        print(final_test_case)
                    if isinstance(msg, UserInputRequestedEvent) and msg.source == 'user_reviewer_agent':
                        print("请输入你的修改意见，或输入同意/Approve")
                        continue
            # 如果需要修改，则要进行汇总
            if update_count > 0:
                print("检测到修改，启动汇总智能体，生成最终版本....")
                summarize_agent = AssistantAgent(
                    name="summarize_agent",
                    model_client=minimax_model,
                    system_message="""
                    你是一个测试用例整理优化专家， 请根据上下文对话信息，结合用户最终的期望，输出优化的最终的测试用例。请严格遵循原始的格式输出规范。
                    """,
                    model_client_stream=True,
                    memory=[testcase_modify_memory]
                )
                summary_stream = summarize_agent.run_stream(
                    task="结合上下文对话信息，参照指定格式输出优化后的完整的测试用例")
                async for msg in summary_stream:
                    if isinstance(msg, ModelClientStreamingChunkEvent):
                        continue
                    if isinstance(msg, TextMessage):
                        if msg.source == 'summarize_agent':
                            final_test_case = msg.content.strip()
                            print(f"最终版本为：\n{final_test_case}")
            # 发送消息给下一个智能体
            await self.publish_message(
                UnstructuredTestCase(unstructured_test=final_test_case),
                topic_id=TopicId(type='api_structure_case', source=self.id.key)
            )
        except Exception as e:
            print(f"设计api测试用例失败: {e}")


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
        self.system_message = api_structure_case_system_prompt(json_format_example)

    UnstructuredMessage = []

    @message_handler
    async def handle_message(self, message: UnstructuredTestCase, ctx: MessageContext) -> None:
        print('*' * 10 + 'apicase_structure_agent' + '*' * 10)
        structure_json_str = ""
        try:
            struction_agent = AssistantAgent(
                name='apicase_structure_agent',
                model_client=json_format_model,
                model_client_stream=False,
                system_message=self.system_message
            )
            task = f"请将下述非结构化测试用例转化为结构化JSON格式：\n\n{message.unstructured_test}"

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
            await self.publish_message(FinalTestCase(final_testcase_json=structure_json_str),
                                       topic_id=TopicId(type="api_case_in_db", source=self.id.key))

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
                await self.publish_message(FinalTestCase(final_testcase_json=fixed_content),
                                           topic_id=TopicId(type="api_case_in_db", source=self.id.key))

            except json.JSONDecodeError as e:
                print(f"修复后的结果不是有效的json{str(e)}")
                raise e
        except Exception as e:
            print(f"API用例结构化出错{e}")


# api_case_into_db
@type_subscription(topic_type="api_case_in_db")
class APITestCaseIntoDBAgent(RoutedAgent):
    """将结构化的测试用例存储到数据库中"""

    def __init__(self):
        super().__init__("apicase_into_db_agent")

    @message_handler
    async def handle_message(self, message: FinalTestCase, ctx: MessageContext) -> None:
        print('*' * 10 + 'apicase_into_db_agent' + '*' * 10)
        print("准备数据入库")
        try:
            test_cases_json = json.loads(message.final_testcase_json)
        except json.JSONDecodeError as e:
            import ast
            data = ast.literal_eval(message.final_testcase_json)
            if isinstance(data, dict) and "testcases" in data:
                test_cases_json = data["testcases"]
            else:
                test_cases_json = data

        validated_cases = [APITestCaseCreate.model_validate(case_data) for case_data in test_cases_json]
        save_count = 0
        for case in validated_cases:
            try:
                await api_testcase_create_controller.create_apicase_with_steps(case_in=case)
                save_count += 1
            except Exception as e:
                print(f"数据验证出错{str(e)}")
                continue
        print(f"数据入库成功，共{save_count}个用例")


async def main():
    api_input = APIDocsInput(api_docs_url="http://localhost:3001/api-docs.json", api_docs_tag="认证",
                             base_url="http://localhost:3001")
    runtime = SingleThreadedAgentRuntime()
    await APIDocsFetcherAgent.register(runtime, 'api_fetch_agent', lambda: APIDocsFetcherAgent())
    await APIAnalyzerAgent.register(runtime, 'api_analyzer_agent', lambda: APIAnalyzerAgent())
    await APICaseDesignerAgent.register(runtime, 'api_designer_agent',
                                        lambda: APICaseDesignerAgent(user_input_func=input))
    await APITestCaseStructureAgent.register(runtime, 'api_structure_agent', lambda: APITestCaseStructureAgent())

    runtime.start()
    await runtime.publish_message(api_input, topic_id=DefaultTopicId("api_content_fetcher"))
    await runtime.stop_when_idle()


asyncio.run(main())
