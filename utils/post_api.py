"""
PostApi：岗位模块接口封装。

覆盖接口（统一前缀 /system/post）：
    list（分页列表：postCode/postName 模糊匹配 + status 精确匹配）/ {id} 详情
    creat / update / delete（批量逗号分隔）/ export（Form 表单参数）

设计要点：
    - 岗位模块共 6 个接口：无 changeStatus，也无数据权限相关接口
      （列表查询不携带数据范围过滤条件）
    - export 使用 data=form 传 Form 表单参数（非 JSON），参数结构与列表查询一致
    - delete 支持批量：后端循环删除，批量中包含已分配岗位时整体事务回滚
"""
class PostApi:
    """岗位模块接口封装：URL 与认证头统一集中管理，用例层仅传业务参数。"""

    def __init__(self, client, token):
        self.client = client
        # 统一组装认证头：岗位模块所有接口均需携带登录后获取的 token
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    # ===== 查询类接口：分页列表 / 详情 =====
    def list(self, **params):
        """岗位分页列表：支持 postCode/postName 模糊筛选、status 精确筛选与分页参数透传。"""
        return self.client.get(
            "system/post/list",
            headers=self.headers,
            params=params
        )

    def detail(self, post_id):
        """岗位详情。"""
        return self.client.get(
            f"system/post/{post_id}",
            headers=self.headers
        )

    # ===== 管理类接口：新增 / 编辑 / 删除 / 导出 =====
    def creat(self, **data):
        """新增岗位：data 含 postCode/postName/postSort/status 等必填字段。"""
        return self.client.post(
            "system/post",
            headers=self.headers,
            json=data
        )

    def update(self, **data):
        """编辑岗位：data 需含 postId 及待修改字段。"""
        return self.client.put(
            "system/post",
            headers=self.headers,
            json=data
        )

    def delete(self, post_ids):
        """删除岗位：支持逗号分隔批量；批量中含已分配岗位时整体事务回滚。"""
        return self.client.delete(
            f"system/post/{post_ids}",
            headers=self.headers
        )

    def export(self, **form):
        """导出岗位列表：以 Form 表单参数提交（data=form），参数结构与列表查询一致。"""
        return self.client.post(
            "system/post/export",
            headers=self.headers,
            data=form
        )
