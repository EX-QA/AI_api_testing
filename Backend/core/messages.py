from pydantic import BaseModel


class UnstructuredTestCase(BaseModel):
    unstructured_text: str


class FinalTestCase(BaseModel):
    final_testcase_json: str
