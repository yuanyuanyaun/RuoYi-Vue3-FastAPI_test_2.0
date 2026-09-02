"""岗位模块-查询 测试用例。

覆盖接口：
    GET /system/post/list        岗位分页列表接口：按条件分页返回岗位数据
    GET /system/post/{post_id}   岗位详情接口：按主键返回单个岗位信息

测试策略：
    列表筛选：仅测岗位特有筛选字段（postCode/postName 为模糊匹配、status 为精确匹配）；
    时间筛选（beginTime/endTime）与分页边界（pageNum/pageSize 特殊值）与用户模块共用同一套
    实现（相同的时间格式解析与分页工具），相关边界场景已在用户模块覆盖，此处不重复。
    分页：每接口保留一条冒烟级正常分页用例，验证分页基础行为。
    路径参数：详情接口覆盖路径参数为空（404）与非数字（422）两类参数层校验场景。
    已知缺陷(xfail)：详情 999 返回 200 全空数据（post_detail_services 的空模型保护），本应报错。
"""

import pytest
import allure
import requests


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("获取岗位分页列表接口")
@allure.description(
    "岗位列表的时间筛选（beginTime/endTime）与分页边界（pageNum/pageSize 特殊值）"
    "与用户模块共用同一套实现（相同的时间格式解析与分页工具），"
    "相关边界场景已在用户模块用例中覆盖（如：时间参数带时分秒或非标准格式时后端返回500、"
    "分页参数为0或负数时后端返回500等已知缺陷），此处不重复测试。"
    "本文件仅测岗位特有筛选字段（postCode/postName/status）。"
)
class TestPostList:
    """岗位分页列表查询用例：仅覆盖岗位特有筛选字段与冒烟级正常分页。"""

    @allure.title("按岗位编码筛选")
    def test_list_filter_by_code(self, post_api):
        """验证按岗位编码筛选时命中目标岗位（postCode 为 LIKE 模糊匹配）。"""
        # postCode 为模糊匹配，种子岗位编码 "ceo" 应被命中且排在结果首位，total 不少于 1
        resp = post_api.list(postCode="ceo")
        # 断言接口调用成功契约：HTTP 200 + 业务 code 200 + 成功标识为 True
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert data["total"] >= 1
        assert data["rows"][0]["postCode"] == "ceo"

    @allure.title("按岗位名称筛选")
    def test_list_filter_by_name(self, post_api):
        """验证按岗位名称筛选时恰好命中唯一目标（postName 为模糊匹配，种子名称唯一）。"""
        # 种子岗位名称「董事长」唯一，模糊匹配应恰好返回 1 条且名称一致
        resp = post_api.list(postName="董事长")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert data["total"] == 1
        assert data["rows"][0]["postName"] == "董事长"

    @allure.title("按状态筛选")
    def test_list_filter_by_status(self, post_api):
        """验证按状态筛选时返回的全部岗位状态均为指定值（status 为精确匹配）。"""
        # status 为精确匹配：用 all 断言保证结果每一行状态均为 "0"，排除混入其他状态的岗位
        resp = post_api.list(status="0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert data["total"] >= 4
        assert all(r["status"] == "0" for r in data["rows"])

    @allure.title("正常分页查询")
    def test_list_pagination(self, post_api):
        """冒烟级分页验证：正常分页参数下每页返回指定条数，total 反映全量数据。"""
        # 每接口保留一条冒烟级分页用例；分页错误边界（pageNum/pageSize 为 0 或负数等已知缺陷）
        # 已在用户模块覆盖，此处不重复
        resp = post_api.list(pageNum=1, pageSize=1)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert len(data["rows"]) == 1
        assert data["total"] >= 4


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("获取岗位详情接口")
class TestPostDetail:
    """岗位详情接口用例：覆盖存在性缺陷与路径参数两类场景。"""

    @pytest.mark.xfail(reason="获取不存在岗位的详情本应报错却返回成功，前端已经做出约束,一般情况下客户端OK")
    @allure.description(
        "实测：查询不存在的岗位时，接口返回 200 且岗位字段全部为空（postId 为 null），"
        "没有返回'岗位不存在'之类的错误提示"
    )
    @allure.title("获取不存在岗位的详情")
    def test_detail_nonexist(self, post_api):
        """已知缺陷验证：查询不存在岗位的详情，期望报错，实际返回 200 全空数据，标记 xfail。"""
        # 缺陷触发点：post_detail_services 对未命中的查询返回空模型（if post else PostModel() 保护），
        # 接口返回 200 且字段全部为空（postId 为 null），无「岗位不存在」提示；
        # 用例断言正常行为契约（code 500），当前实际失败故标记 xfail
        resp = post_api.detail(999)
        assert resp.json()["code"] == 500

    @allure.title("详情路径参数为空")
    def test_detail_empty_path(self, post_api):
        """路径参数校验：详情路径参数为空字符串时不匹配 /{post_id} 路由，返回 HTTP 404。"""
        # 空路径无法路由到详情端点，由框架层返回 404，
        # requests 抛出 HTTPError，捕获后断言响应状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            post_api.detail("")
        assert e.value.response.status_code == 404

    @allure.title("详情路径参数非数字")
    def test_detail_non_numeric(self, post_api):
        """路径参数校验：详情路径参数为非数字时，FastAPI 参数层 int 解析失败，返回 HTTP 422。"""
        # "abc" 无法解析为 int，由参数层（FastAPI 类型转换）返回 422，无内部错误泄漏
        with pytest.raises(requests.exceptions.HTTPError) as e:
            post_api.detail("abc")
        assert e.value.response.status_code == 422
