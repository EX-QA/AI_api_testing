from typing import List

from loguru import logger


async def generate_api_scripts_by_ids(ids: List[int]):
    """
    根据用例ids生成api脚本
    :param ids:
    :return:
    """
    try:
        selected_api_case = await api_testcase_create_controller.get_api_case_by_ids(ids)
        logger.info(f"成功从数据库获取{len(selected_api_case)}条测试用例")

        formatted_cases =[]
        for case in selected_api_case:
    except Exception as e:
        raise e