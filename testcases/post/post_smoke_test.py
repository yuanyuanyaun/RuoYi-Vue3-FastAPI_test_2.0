"""岗位模块-冒烟 测试用例。

覆盖接口：
    GET    /system/post/list            岗位分页列表接口：按条件分页返回岗位数据
    POST   /system/post                 新增岗位接口：新增岗位并落库
    PUT    /system/post                 编辑岗位接口：按主键更新岗位字段
    GET    /system/post/{post_id}       岗位详情接口：按主键返回单个岗位信息
    DELETE /system/post/{post_ids}      删除岗位接口：按主键批量删除（支持逗号分隔）

测试策略：
    正向主链路闭环：新增 → 列表 → 编辑 → 详情 → 删除，覆盖岗位模块核心正向链路。
    数据库校验：新增/编辑后直查 sys_post 表，验证业务字段真实落库。
    物理删除校验：岗位表无 del_flag 字段，删除为物理删除，删除后按主键直查计数应为 0。
    用例之间存在数据依赖：类级共享 post_code/post_name，test_post_list_success 从列表回读
    post_id 存入类变量，后续编辑/详情/删除用例复用，因此本类用例必须按定义顺序执行，
    不可单独或乱序运行。
"""

import pytest
import allure
import time


@pytest.mark.post
@pytest.mark.smoke
@allure.feature("岗位模块")
class TestPostSmoke:
    """岗位冒烟闭环用例：覆盖新增 → 列表 → 编辑 → 详情 → 删除全链路正向场景，类级共享编码/名称/post_id。"""

    # 类级共享变量：编码/名称以时间戳毫秒值命名保证唯一性；post_id 由列表用例从查询结果回读，
    # 供后续编辑/详情/删除用例复用（冒烟用例存在顺序依赖，需按定义顺序执行）
    post_code = f"code_{int(time.time() * 1000)}"
    post_name = f"name_{int(time.time() * 1000)}"
    post_id = None

    @allure.story("新增列表接口")
    @allure.title("最多字段的新增岗位")
    def test_post_creat_success(self, post_api, mysql):
        """验证一次性提交全部业务字段新增岗位成功，且各字段真实落库。"""
        # 构造新增请求体：提交岗位全部业务字段（编码/名称/排序/状态/备注），
        # post_code/post_name 取类级唯一值，验证接口对完整字段组合的处理能力
        resp = post_api.creat(
            **{
                "postCode": TestPostSmoke.post_code,
                "postName": TestPostSmoke.post_name,
                "postSort": 9,
                "status": "0",
                "remark": "备注"
            }
        )
        # 断言新增成功契约：业务 code 200 + 成功标识为 True + 提示语「新增成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "新增成功"
        # 数据库校验：按唯一 post_code 反查 sys_post 表，逐字段核对新增数据真实落库
        row = mysql["one"](
            "select post_code,post_name,post_sort,status,remark "
            "from sys_post where post_code=%s",(TestPostSmoke.post_code,)
        )
        assert row["post_code"] == TestPostSmoke.post_code
        assert row["post_name"] == TestPostSmoke.post_name
        assert row["post_sort"] == 9
        assert row["status"] == "0"
        assert row["remark"] == "备注"

    @allure.story("列表查询岗位接口")
    @allure.title("默认条件获取岗位列表成功")
    def test_post_list_success(self, post_api):
        """验证默认条件下分页列表返回全部岗位，且新建岗位以完整字段出现在列表中。"""
        # 默认分页列表：种子岗位 4 个，加上本用例新建的岗位，total 应不少于 4
        resp = post_api.list()
        # 断言列表接口调用成功契约：业务 code 200 + 成功标识为 True + 提示语「操作成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "操作成功"
        assert resp.json()["total"] >= 4
        # 遍历列表按编码与名称双条件匹配新建岗位，核对字段后回读 postId 存入类变量，
        # 作为编辑/详情/删除用例的数据依赖
        for data in resp.json()["rows"]:
            if (data["postCode"] == TestPostSmoke.post_code
            and data["postName"] == TestPostSmoke.post_name):
                assert data["postSort"] == 9
                assert data["status"] == "0"
                assert data["remark"] == "备注"
                TestPostSmoke.post_id = data["postId"]

    @allure.story("编辑岗位接口")
    @allure.title("最大字段编辑岗位")
    def test_post_update_success(self, post_api, mysql):
        """验证编辑岗位时全字段更新成功且真实落库。"""
        # 构造编辑请求体：postId 复用列表用例回读的类变量；编码/名称加 update_ 前缀、排序 10、
        # 状态切为停用 "1"、备注更换，全字段变更验证编辑能力
        resp = post_api.update(
            **{
                "postId": TestPostSmoke.post_id,
                "postCode": f"update_{TestPostSmoke.post_code}",
                "postName": f"update_{TestPostSmoke.post_name}",
                "postSort": 10,
                "status": "1",
                "remark": "更改备注"
            }
        )
        # 断言编辑成功契约：业务 code 200 + 成功标识为 True + 提示语「更新成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "更新成功"
        # 数据库校验：按 post_id 反查 sys_post 表，逐字段核对编辑结果真实落库
        row = mysql["one"](
            "select post_code,post_name,post_sort,status,remark "
            "from sys_post where post_id=%s",(TestPostSmoke.post_id,)
        )
        assert row["post_code"] == f"update_{TestPostSmoke.post_code}"
        assert row["post_name"] == f"update_{TestPostSmoke.post_name}"
        assert row["post_sort"] == 10
        assert row["status"] == "1"
        assert row["remark"] == "更改备注"

    @allure.story("详细查询岗位接口")
    @allure.title("成功查询指定岗位数据")
    def test_post_detail_success(self, post_api):
        """验证按主键查询返回编辑后的岗位数据，与数据库校验互补确认 API 层数据一致性。"""
        # 按类级 post_id 调详情接口，核对编辑后的字段（API 层验证，与库表校验互为印证）
        resp = post_api.detail(TestPostSmoke.post_id)
        # 断言详情接口调用成功契约：业务 code 200 + 成功标识为 True + 提示语「操作成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "操作成功"
        # 逐字段核对详情返回的编辑后岗位数据（排序/状态/编码/名称）
        assert resp.json()["data"]["postSort"] == 10
        assert resp.json()["data"]["status"] == "1"
        assert resp.json()["data"]["postCode"] == f"update_{TestPostSmoke.post_code}"
        assert resp.json()["data"]["postName"] == f"update_{TestPostSmoke.post_name}"

    @allure.story("删除岗位接口")
    @allure.title("删除指定岗位成功")
    def test_post_delete_success(self, post_api, mysql):
        """验证删除岗位成功后列表复查不可见，且数据库层面为物理删除。"""
        # 按类级 post_id 调删除接口，验证删除操作本身成功
        resp = post_api.delete(TestPostSmoke.post_id)
        # 断言删除成功契约：业务 code 200 + 成功标识为 True + 提示语「删除成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "删除成功"
        # API 复查：按编辑后的编码与名称筛选列表，total 与 rows 均为空（删除后查询透明）
        data = post_api.list(
            postCode=f"update_{TestPostSmoke.post_code}",
            postName=f"update_{TestPostSmoke.post_name}"
        ).json()
        assert data["total"] == 0
        assert len(data["rows"]) == 0
        # 数据库校验：岗位表无 del_flag 字段，删除为物理删除，按 post_id 直查计数应为 0
        row = mysql["one"]("select count(*) as cnt from sys_post where post_id=%s",
                           (TestPostSmoke.post_id,))
        assert row["cnt"] == 0
