"""部门模块-冒烟 测试用例。

覆盖接口：
    POST   /system/dept               新增部门接口：新增部门并落库，返回新增成功提示
    GET    /system/dept/list          部门列表接口：返回部门树数据（不分页，data 为数组）
    PUT    /system/dept               编辑部门接口：按主键更新部门全部字段
    GET    /system/dept/{dept_id}     部门详情接口：按主键返回单个部门信息
    DELETE /system/dept/{dept_ids}    删除部门接口：按主键软删除部门（del_flag 置 2）

测试策略：
    正向主链路闭环：新增 → 列表 → 编辑 → 详情 → 删除，覆盖部门模块核心正向链路。
    数据库校验：新增/编辑后直查 sys_dept 表，验证业务字段真实落库及 ancestors 祖先链计算正确。
    软删除校验：删除后验证 sys_dept.del_flag 置为 "2"，且列表接口不再返回该部门。
    用例之间存在数据依赖：test_dept_creat_success 固化 dept_name，test_dept_list_success
    从列表回读 dept_id 存入类变量，后续编辑/详情/删除用例复用该 dept_id，
    因此本类用例必须按定义顺序执行，不可单独或乱序运行。
"""

import pytest
import allure
import time


@pytest.mark.dept
@pytest.mark.smoke
@allure.feature("部门模块")
class TestDeptSmoke:
    """部门冒烟闭环用例：覆盖新增 → 列表 → 编辑 → 详情 → 删除全链路正向场景，类级共享 dept_name/dept_id。"""

    # 类级共享变量：dept_name 以时间戳毫秒值命名保证唯一性，避免与既有数据冲突；
    # dept_id 由列表用例从查询结果回读，供后续编辑/详情/删除用例复用（冒烟用例存在顺序依赖）
    dept_name = f"dept_{int(time.time() * 1000)}"
    dept_id = None

    @allure.story("新增部门接口")
    @allure.title("最多字段的新增部门")
    def test_dept_creat_success(self, dept_api, mysql):
        """验证一次性提交全部业务字段新增部门成功，且各字段真实落库、ancestors 祖先链计算正确。"""
        # 构造新增请求体：提交部门全部业务字段（名称/上级部门/排序/负责人/电话/邮箱/状态），
        # 其中 dept_name 取类级唯一值，parentId 固定指向种子部门 100（集团总公司），
        # 验证接口对完整字段组合的处理能力
        resp = dept_api.creat(
            **{
                "deptName": TestDeptSmoke.dept_name,
                "parentId": 100,
                "orderNum": 9,
                "leader": "冒烟负责人",
                "phone": "13800138000",
                "email": "smoke@qq.com",
                "status": "0"
            }
        )
        # 断言新增成功契约：业务 code 200 + 成功标识为 True + 提示语「新增成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "新增成功"
        # 数据库校验：按唯一 dept_name 反查 sys_dept 表，逐字段核对新增数据真实落库；
        # ancestors 期望为 "0,100"，验证祖先链由「顶级节点 0 + 父部门 100」拼接生成
        row = mysql["one"](
            "select dept_name,parent_id,order_num,leader,phone,email,status,ancestors "
            "from sys_dept where dept_name=%s", (TestDeptSmoke.dept_name,)
        )
        assert row["dept_name"] == TestDeptSmoke.dept_name
        assert row["parent_id"] == 100
        assert row["order_num"] == 9
        assert row["leader"] == "冒烟负责人"
        assert row["phone"] == "13800138000"
        assert row["email"] == "smoke@qq.com"
        assert row["status"] == "0"
        assert row["ancestors"] == "0,100"

    @allure.story("列表查询部门接口")
    @allure.title("默认条件获取部门列表成功")
    def test_dept_list_success(self, dept_api):
        """验证默认条件下部门列表接口返回全部部门，且新建部门以完整字段出现在列表中。"""
        # 部门列表为不分页接口（返回 data 数组），此处以默认条件获取全量部门数据
        resp = dept_api.list()
        # 断言列表接口调用成功契约：业务 code 200 + 成功标识为 True + 提示语「操作成功」+ 数据非空
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "操作成功"
        assert resp.json()["data"]
        # 遍历列表按类级 dept_name 匹配新建部门，核对列表返回字段与新增请求一致；
        # 命中后回读 deptId 存入类变量，作为编辑/详情/删除用例的数据依赖
        for data in resp.json()["data"]:
            if data["deptName"] == TestDeptSmoke.dept_name:
                assert data["parentId"] == 100
                assert data["orderNum"] == 9
                assert data["leader"] == "冒烟负责人"
                assert data["phone"] == "13800138000"
                assert data["email"] == "smoke@qq.com"
                assert data["status"] == "0"
                TestDeptSmoke.dept_id = data["deptId"]

    @allure.story("编辑部门接口")
    @allure.title("最大字段编辑部门")
    def test_dept_update_success(self, dept_api, mysql):
        """验证编辑部门时全字段更新成功且真实落库，父部门未变更时 ancestors 祖先链保持不变。"""
        # 构造编辑请求体：deptId 复用列表用例回读的类变量；除父部门外全字段变更
        #（名称加 update_ 前缀、排序 10、负责人/电话/邮箱更换、状态切为停用 "1"）
        resp = dept_api.update(
            **{
                "deptId": TestDeptSmoke.dept_id,
                "deptName": f"update_{TestDeptSmoke.dept_name}",
                "parentId": 100,
                "orderNum": 10,
                "leader": "编辑负责人",
                "phone": "13900139000",
                "email": "edit_smoke@qq.com",
                "status": "1"
            }
        )
        # 断言编辑成功契约：业务 code 200 + 成功标识为 True + 提示语「更新成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "更新成功"
        # 数据库校验：按 dept_id 反查 sys_dept 表，逐字段核对编辑结果真实落库；
        # 父部门仍为 100，故 ancestors 保持 "0,100" 不变（祖先链仅随父级变更而重算）
        row = mysql["one"](
            "select dept_name,parent_id,order_num,leader,phone,email,status,ancestors "
            "from sys_dept where dept_id=%s", (TestDeptSmoke.dept_id,)
        )
        assert row["dept_name"] == f"update_{TestDeptSmoke.dept_name}"
        assert row["parent_id"] == 100
        assert row["order_num"] == 10
        assert row["leader"] == "编辑负责人"
        assert row["phone"] == "13900139000"
        assert row["email"] == "edit_smoke@qq.com"
        assert row["status"] == "1"
        assert row["ancestors"] == "0,100"

    @allure.story("详细查询部门接口")
    @allure.title("成功查询指定部门数据")
    def test_dept_detail_success(self, dept_api):
        """验证按主键查询返回编辑后的完整部门数据，与数据库校验互补确认 API 层数据一致性。"""
        # 按类级 dept_id 调详情接口，核对编辑后的全字段（API 层验证，与库表校验互为印证）
        resp = dept_api.detail(TestDeptSmoke.dept_id)
        # 断言详情接口调用成功契约：业务 code 200 + 成功标识为 True + 提示语「操作成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "操作成功"
        # 逐字段核对详情返回的编辑后部门数据（名称/父级/排序/负责人/电话/邮箱/状态）
        assert resp.json()["data"]["deptName"] == f"update_{TestDeptSmoke.dept_name}"
        assert resp.json()["data"]["parentId"] == 100
        assert resp.json()["data"]["orderNum"] == 10
        assert resp.json()["data"]["leader"] == "编辑负责人"
        assert resp.json()["data"]["phone"] == "13900139000"
        assert resp.json()["data"]["email"] == "edit_smoke@qq.com"
        assert resp.json()["data"]["status"] == "1"

    @allure.story("删除部门接口")
    @allure.title("删除指定部门成功")
    def test_dept_delete_success(self, dept_api, mysql):
        """验证删除部门成功后该部门在列表中不可见，且数据库层面执行软删除（del_flag 置 2）。"""
        # 按类级 dept_id 调删除接口，验证删除操作本身成功
        resp = dept_api.delete(TestDeptSmoke.dept_id)
        # 断言删除成功契约：业务 code 200 + 成功标识为 True + 提示语「删除成功」
        assert resp.json()['code'] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "删除成功"
        # API 复查：按编辑后的名称筛选列表，确认该部门已不再返回（软删除对查询透明）
        delete_resp = dept_api.list(deptName=f"update_{TestDeptSmoke.dept_name}")
        for data in delete_resp.json()["data"]:
            assert data["deptName"] != f"update_{TestDeptSmoke.dept_name}"
        # 数据库校验：按 dept_id 直查 sys_dept.del_flag，期望 "2"，
        # 验证删除为软删除（逻辑删除）而非物理删除，与含下级/含用户时的拦截逻辑同源
        row = mysql["one"]("select del_flag from sys_dept where dept_id=%s",
                           (TestDeptSmoke.dept_id,))
        assert row["del_flag"] == "2"
