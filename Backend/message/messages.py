from typing import List, Dict, Any, Optional, Union

from pydantic import BaseModel, Field


class APIDocsInput(BaseModel):
    """API 文档/url 输入模型参数"""
    api_docs_url: Optional[str] = Field(None, description="API 文档/url")
    api_docs_tag: Optional[str] = Field(None, description="API 的模块")
    base_url: str = Field(..., description="api的host")
    uploaded_file: Optional[list[str]] = Field(None, description="上传的API文档路径列表")
    api_doc_supplement: Optional[str] = Field(None, description="API文档接口补充说明")
    test_focus: Optional[str] = Field(None, description="测试用例设计说明")
    api_doc_content: Optional[Dict[str, Any]] = Field(None, description="API文档内容")


class APIAnalysisResult(BaseModel):
    """API分析结果消息类型"""
    api_docs_url: Optional[str] = Field(None, description="API 文档/URL")
    base_url: str = Field(..., description="api的host")
    uploaded_file: Optional[list[str]] = Field(None, description="上传的API文档路径列表")
    api_doc_supplement: Optional[str] = Field(None, description="API文档接口补充说明")
    test_focus: Optional[str] = Field(None, description="测试用例设计说明")
    api_analysis_result: Union[str, List[str]] = Field(..., description="API分析结果")


class UnstructuredTestCase(BaseModel):
    unstructured_test: str


class FinalTestCase(BaseModel):
    final_testcase_json: str


class SelectedAPICaseInput(BaseModel):
    selected_api_case: List[Dict[str, Any]]
    case_ids: List[int]
    # project_id : Optional[int] = Field(None, description="所属项目id")
