from tortoise.transactions import atomic

from Backend.models.model import APITestCase, APITestStep
from Backend.schemas.api_case import APITestCaseCreate


class APITestCaseController:

    @atomic
    async def create_apicase_with_steps(self, case_in: APITestCaseCreate) -> APITestCase:
        """
        包含所有步骤的api测试用例
        :param case_in:
        :return:
        """

        try:
            # 创建测试用例 入库
            case_data = case_in.model_dump(exclude={"steps"}, exclude_none=False)
            new_case = await APITestCase.create(**case_data)

            # 测试步骤入库
            if case_in.steps:
                for step_data in case_in.steps:
                    await APITestStep.create(
                        case=new_case, **step_data.model_dump()
                    )
            print(f"{new_case.title}成功入库")
            return new_case
        except Exception as e:
            raise e


api_testcase_create_controller = APITestCaseController()
