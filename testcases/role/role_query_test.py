"""角色模块-查询 测试用例。

覆盖接口：
    GET /system/role/list       获取角色分页列表接口：分页返回角色列表，支持按名称/权限字符/状态筛选
    GET /system/role/{role_id}  获取角色详情接口：返回指定角色的完整字段

测试策略：
    正向：按角色名称/权限字符/状态筛选，以及正常分页查询，验证筛选与分页契约。
    去重说明：时间筛选与分页边界与用户模块共用同一套实现（相同的时间解析与分页工具），
    对应已知缺陷已在用户模块用例中覆盖，本文件不重复测试，仅测角色特有筛选字段。
    已知缺陷(xfail)：查询不存在角色的详情返回 200 且字段全空（role_detail_services 空模型保护），
    期望返回错误码 500 但实际假成功。
    反向：详情路径参数为空串（404）、非数字（422），验证框架层参数校验行为。
"""

import pytest
import allure
import requests



@pytest.mark.role
@allure.feature("角色模块")
@allure.story("获取角色分页列表接口")
@allure.description(
    "角色列表的时间筛选（beginTime/endTime）与分页边界（pageNum/pageSize 特殊值）"
    "与用户模块共用同一套实现（相同的时间格式解析与分页工具），"
    "相关边界场景已在用户模块用例中覆盖（如：时间参数带时分秒或非标准格式时后端返回500、"
    "分页参数为0或负数时后端返回500等已知缺陷），此处不重复测试。"
    "本文件仅测角色特有筛选字段（roleName/roleKey/status）。"
)
class TestRoleList:
    """获取角色分页列表接口（GET /system/role/list），仅覆盖角色特有的筛选与分页字段。"""

    @allure.title("按角色名称筛选")
    def test_list_filter_by_name(self, role_api):
        """验证按角色名称筛选：LIKE 模糊匹配命中唯一的种子角色"超级管理员"。"""
        # roleName 是 LIKE 模糊匹配；种子角色"超级管理员"应恰好命中 1 条
        resp = role_api.list(roleName="超级管理员")
        # 断言接口成功契约：HTTP 200 + 业务 code 200 + 成功标识为 True
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # 断言筛选命中唯一结果：total=1 且首行名称与筛选条件一致
        assert data["total"] == 1
        assert data["rows"][0]["roleName"] == "超级管理员"

    @allure.title("按权限字符筛选")
    def test_list_filter_by_key(self, role_api):
        """验证按权限字符筛选：LIKE 模糊匹配命中唯一的种子角色 admin。"""
        # roleKey 是 LIKE 模糊匹配；种子角色权限字符 "admin" 应恰好命中 1 条
        resp = role_api.list(roleKey="admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        assert data["total"] == 1
        assert data["rows"][0]["roleKey"] == "admin"

    @allure.title("按状态筛选")
    def test_list_filter_by_status(self, role_api):
        """验证按状态筛选：精确匹配返回的全部行状态均为指定值。"""
        # status 是精确匹配（不是模糊）：返回的所有行状态都应为 "0"
        resp = role_api.list(status="0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # 预置角色中启用（status="0"）角色数 >= 2，且每行状态均等于筛选值
        assert data["total"] >= 2
        assert all(r["status"] == "0" for r in data["rows"])

    @allure.title("正常分页查询")
    def test_list_pagination(self, role_api):
        """验证正常分页查询：返回行数与 pageSize 一致，且总数基线保证存在后续页。"""
        # 正常分页（每页 1 条冒烟级用例；分页错误边界已在用户模块覆盖，此处不重复）
        resp = role_api.list(pageNum=1, pageSize=1)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # 断言分页生效：返回行数等于 pageSize=1，且数据总数 >= 2 保证分页有后续页
        assert len(data["rows"]) == 1
        assert data["total"] >= 2


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("获取角色详情接口")
class TestRoleDetail:
    """获取角色详情接口（GET /system/role/{role_id}），覆盖不存在角色与非法路径参数两类反向场景。"""

    @pytest.mark.xfail(reason="获取不存在角色的详情本应报错却返回成功，前端已经做出约束,一般情况下客户端OK")
    @allure.description(
        "实测：查询不存在的角色时，接口返回 200 且角色字段全部为空（roleId 为 null），"
        "没有返回'角色不存在'之类的错误提示"
    )
    @allure.title("获取不存在角色的详情")
    def test_detail_nonexist(self, role_api):
        """验证已知缺陷：查询不存在角色本应报错，实际返回 200 且字段全空（假成功）。"""
        # role_detail_services 有 if role else RoleModel() 空模型保护 → 200 全空（缺陷），
        # 期望返回错误码 500，断言不成立 → xfail
        resp = role_api.get_detail(999)
        assert resp.json()["code"] == 500

    @allure.title("详情路径参数为空")
    def test_detail_empty_path(self, role_api):
        """验证反向场景：详情路径参数为空串时不匹配路由，被 HTTP 层拦截返回 404。"""
        # 空路径：不匹配 /{role_id} 路由 → HTTP 404，由框架层直接拦截
        with pytest.raises(requests.exceptions.HTTPError) as e:
            role_api.get_detail("")
        assert e.value.response.status_code == 404


    @allure.title("详情路径参数为非法值")
    def test_detail_non_numeric(self, role_api):
        """验证反向场景：路径参数为非数字时 FastAPI 参数层 int 解析失败，返回 422。"""
        # 非数字：FastAPI 参数层 int 解析失败 → HTTP 422（干净的参数校验错误，无内部信息泄漏）
        with pytest.raises(requests.exceptions.HTTPError) as e:
            role_api.get_detail("abc")
        assert e.value.response.status_code == 422
