import json

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_core import type_subscription, RoutedAgent, message_handler, MessageContext, TopicId

from Backend.api_agent.llm_models.llm_models import json_format_model
from Backend.api_agent.prompt_words.api_agent_prompt import api_structure_case_prompt, fix_agent_prompt
from Backend.controller.api_test_case import api_testcase_create_controller
from Backend.core.messages import FinalTestCase
from Backend.schemas.api_case import APITestCaseCreate


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
            await self.publish_message(FinalTestCase(final_testcase_json=out_result),
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
