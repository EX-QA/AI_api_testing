from tortoise import models, fields


class APITestStep(models.Model):
    """API测试步骤表模型"""
    case = fields.ForeignKeyField("models.APITestCase", related_name="steps", on_delete=fields.CASCADE,
                                  description='关联的测试用例')
    step_name = fields.CharField(255, description="步骤名称名称")
    http_method = fields.CharField(255, description="http请求方法")
    step_index = fields.IntField(description="步骤序号")
    url = fields.CharField(1025, description="请求路径")
    headers = fields.JSONField(null=True, description="请求头")
    body = fields.JSONField(null=True, description="请求体")
    expected_status_code = fields.IntField(default=200, description="期望的http状态码")
    assertions = fields.JSONField(null=True, description="断言列表")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "api_test_steps"
        ordering = ["-created_at"]


class APITestCase(models.Model):
    """API测试用例表模型"""
    title = fields.CharField(255, description="测试用例标题")
    description = fields.TextField(null=True, description="测试用例描述")
    api_url = fields.CharField(1025, description="被测接口的url")
    base_url = fields.CharField(255, description="被测接口的base_url")
    project_id = fields.IntField(null=True, description="所属项目id")
    priority = fields.CharField(max_length=20, default="Medium", description="优先级")
    tags = fields.JSONField(null=True, description="标签")
    preconditions = fields.TextField(null=True, description="前置条件")
    postconditions = fields.TextField(null=True, description="后置条件")
    client_id = fields.CharField(255, default=111, description="客户端id")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    steps = fields.ReverseRelation["APITestStep"]

    class Meta:
        table = "api_test_cases"
        ordering = ["-created_at"]
