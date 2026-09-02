"""
function：测试数据工厂与认证辅助函数（通用工具层）。

模块构成：
    auth(token)  生成 Bearer 认证头，供所有需要认证的接口封装复用
    make_xxx()   各业务模块的测试数据工厂（工厂模式）：
                 按模块最小必填字段构造创建数据，字段值以毫秒时间戳保证唯一，
                 用例层通过 overrides 关键字参数覆盖指定字段

工厂设计要点：
    - 仅构造模型层 @NotBlank 或数据库层必需的字段，其余字段由用例按需覆盖
    - 时间戳在每次调用时动态生成，同一测试运行内多次调用也不会命中唯一性约束
    - 工厂函数只负责构造数据，不负责创建与清理；
      数据的创建与级联清理由 conftest 中的 creat_xxx 夹具完成（夹具自清理策略）
"""
import time


def auth(token):
    """生成 Bearer 认证头，JWT token 经此注入每次需认证的请求。"""
    return {
        "Authorization":
            f"Bearer {token}"
    }


def make_user(**overrides):
    """构造用户创建数据：最小必填 userName/nickName/password。

    字段必填依据：
        userName  模型层 @NotBlank 必填；
        nickName  数据库层必填，缺失时后端插入抛异常并返回 HTTP 500；
        password  service 层必填，缺失时创建流程中断；
    其余字段（如 phonenumber/email/status）由用例通过 overrides 按需覆盖。
    """
    ts = int(time.time() * 1000)
    base = {
        "userName": f"user_{ts}",
        "nickName": f"nick_{ts}",
        "password": "Test@123456"
    }
    base.update(overrides)
    return base


def make_role(**overrides):
    """构造角色创建数据：最小必填 roleName/roleKey/roleSort/status/menuIds。

    字段必填依据：
        roleName/roleKey  模型层必填；
        status            数据库层必填（模型层仅 Literal 约束、无 NotBlank），
                          缺失时后端返回 HTTP 500；
        menuIds           默认挂载的菜单权限，赋值为菜单种子数据 id 列表；
        roleSort          排序值，默认 9。
    """
    ts = int(time.time() * 1000)
    base = {
        "roleName": f"role_{ts}",
        "roleKey": f"key_{ts}",
        "roleSort": 9,
        "status": "0",
        "menuIds": [1, 2, 100]
    }
    base.update(overrides)
    return base


def make_post(**overrides):
    """构造岗位创建数据：最小必填 postCode/postName/postSort/status。

    字段必填依据：postCode/postName 为业务唯一键（后端存在唯一性校验），
    postSort 为排序值，status 为状态（"0" 正常），缺失任一字段创建流程中断。
    """
    ts = int(time.time() * 1000)
    base = {
        "postCode": f"code_{ts}",
        "postName": f"岗位_{ts}",
        "postSort": 1,
        "status": "0"
    }
    base.update(overrides)
    return base


def make_dept(**overrides):
    """构造部门创建数据：最小必填 deptName/orderNum/parentId。

    字段必填依据：
        parentId 不可省略——后端需取父部门记录拼接 ancestors 祖先链，
                 父部门缺失时抛 AttributeError 并返回 HTTP 500（已记录为已知缺陷）；
        默认挂载 parentId=100（集团总公司，状态正常），保证祖先链合法可拼接。
    """
    ts = int(time.time() * 1000)
    base = {
        "deptName": f"部门_{ts}",
        "parentId": 100,
        "orderNum": 1
    }
    base.update(overrides)
    return base


def make_menu(**overrides):
    """构造菜单创建数据：最小必填 menuName/orderNum/menuType（模型层三个 @NotBlank）。

    默认值设计：
        parentId 不传则缺省 0，表示顶级菜单；
        path/component 留空时，后端路由冲突检查直接跳过，避免与既有路由冲突。
    """
    ts = int(time.time() * 1000)
    base = {
        "menuName": f"菜单_{ts}",
        "orderNum": 1,
        "menuType": "C"
    }
    base.update(overrides)
    return base
