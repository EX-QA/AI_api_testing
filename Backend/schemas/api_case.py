from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class APITestStepCase(BaseModel):
    """
    api测试步骤基础模型
    """
    step_name: str = Field(..., description="步骤名称名称")
    http_method: str = Field(..., description="http请求方法")
    step_index: int = Field(..., description="步骤序号")
    url: str = Field(..., description="请求路径")
    headers: Optional[Dict[str, Any]] = Field(None, description="请求头")
    body: Optional[Dict[str, Any]] = Field(None, description="请求体")
    expected_status_code: int = Field(200, description="期望的http状态码")
    assertions: Optional[List[str]] = Field(None, description="断言")


class APITestCaseBase(BaseModel):
    """
    api测试用例基础模型
    """
    title: str = Field(..., description="测试用例标题")
    description: Optional[str] = Field(None, description="测试用例描述")
    api_url: str = Field(..., description="被测接口的url")
    base_url: str = Field(..., description="被测接口的base_url")
    project_id: Optional[int] = Field(None, description="所属项目id")
    priority: str = Field("Medium", description="优先级")
    tags: Optional[List[str]] = Field(None, description="标签")
    preconditions: Optional[str] = Field(None, description="前置条件")
    postconditions: Optional[str] = Field(None, description="后置条件")
    steps: List[APITestStepCase] = Field(..., description="测试步骤")


class APITestCaseCreate(APITestCaseBase):
    """
    创建api测试用例
    """
    pass
