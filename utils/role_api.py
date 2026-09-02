"""
RoleApi：角色模块接口封装。

覆盖接口（统一前缀 /system/role）：
    查询类：list（分页列表）/ {id}（详情）/ deptTree/{id}（数据权限部门树）
    管理类：creat / update / delete（批量逗号分隔）/ changeStatus / dataScope（数据权限）
    角色-用户分配：authUser/allocatedList（已分配用户）、unallocatedList（未分配用户）、
                  selectAll（分配，追加语义）、cancel（取消单个，body 参数）、
                  cancelAll（批量取消，query 参数）

设计要点：
    - 分配类接口的传参位置不统一，需严格区分：
        selectAll / cancelAll 使用 query 参数（params），cancel 使用 body 参数（json）
    - selectAll 为"追加"语义（已存在的分配自动跳过），
      与用户模块 authRole 的"替换"语义相反
    - delete 支持逗号分隔的批量 id（如 "1,2"），后端循环删除并整体事务回滚
"""
class RoleApi:
    """角色模块接口封装：URL、认证头与请求体结构集中管理，用例层仅传业务参数。"""

    def __init__(self, client, token):
        self.client = client
        # 统一组装认证头：角色模块所有接口均需携带登录后获取的 token
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    # ===== 查询类接口：分页列表 / 详情 / 数据权限部门树 =====
    def list(self, **params):
        """角色分页列表：支持 roleName/roleKey/status 筛选与分页参数透传。"""
        return self.client.get(
            "system/role/list",
            headers=self.headers,
            params=params
        )

    def get_detail(self, role_id):
        """角色详情：获取指定角色的基本信息与菜单权限。"""
        return self.client.get(
            f"system/role/{role_id}",
            headers=self.headers
        )

    def get_dept_tree(self, role_id):
        """数据权限部门树：展示指定角色数据权限范围内的部门层级。"""
        return self.client.get(
            f"system/role/deptTree/{role_id}",
            headers=self.headers
        )

    # ===== 管理类接口：新增 / 编辑 / 删除 / 启用停用 / 数据权限 =====
    def creat(self, **data):
        """新增角色：data 含 roleName/roleKey/menuIds 等必填字段。"""
        return self.client.post(
            "system/role",
            headers=self.headers,
            json=data
        )

    def update(self, **data):
        """编辑角色：data 需含 roleId 及待修改字段。"""
        return self.client.put(
            "system/role",
            headers=self.headers,
            json=data
        )

    def delete(self, role_ids):
        """删除角色：支持逗号分隔的角色 id 列表批量删除，后端整体事务回滚。"""
        return self.client.delete(
            f"system/role/{role_ids}",
            headers=self.headers
        )

    def change_status(self, role_id, status):
        """修改角色状态：status 为 "0"（正常）/ "1"（停用）。"""
        return self.client.put(
            "system/role/changeStatus",
            headers=self.headers,
            json={
                "roleId": role_id,
                "status": status
            }
        )

    def update_data_scope(self, role_id, data_scope, dept_ids=None):
        """编辑数据权限：dataScope 指定权限范围，dept_ids 为自定义范围时的部门 id 列表。"""
        body = {
            "roleId": role_id,
            "dataScope": data_scope
        }
        if dept_ids:
            # 自定义数据权限（dataScope=5）时才携带 deptIds，其余范围无需部门列表
            body["deptIds"] = dept_ids
        return self.client.put(
            "system/role/dataScope",
            headers=self.headers,
            json=body
        )

    # ===== 角色-用户分配类接口：追加分配 / 取消分配 =====
    def allocated_users(self, role_id, **params):
        """已分配用户列表：展示当前已分配给该角色的用户。"""
        return self.client.get(
            "system/role/authUser/allocatedList",
            headers=self.headers,
            params={
                "roleId": role_id,
                **params
            }
        )

    def unallocated_users(self, role_id, **params):
        """未分配用户列表：展示尚未分配给该角色的用户（可分配候选）。"""
        return self.client.get(
            "system/role/authUser/unallocatedList",
            headers=self.headers,
            params={
                "roleId": role_id,
                **params
            }
        )

    def assign_users(self, role_id, user_ids):
        """分配用户给角色（query 参数）：追加语义，已存在的分配自动跳过。"""
        return self.client.put(
            "system/role/authUser/selectAll",
            headers=self.headers,
            params={
                "roleId": role_id,
                "userIds": user_ids
            }
        )

    def cancel_user(self, role_id, user_id):
        """取消单个用户分配（body 参数）。"""
        return self.client.put(
            "system/role/authUser/cancel",
            headers=self.headers,
            json={
                "roleId": role_id,
                "userId": user_id
            }
        )

    def cancel_all_users(self, role_id, user_ids):
        """批量取消用户分配（query 参数）。"""
        return self.client.put(
            "system/role/authUser/cancelAll",
            headers=self.headers,
            params={
                "roleId": role_id,
                "userIds": user_ids
            }
        )
