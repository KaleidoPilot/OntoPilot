import bcrypt

def get_password_hash(password: str) -> str:
    """
    获取密码的哈希值
    :param password: 明文密码
    :return: 哈希后的密码字符串
    """
    # bcrypt 要求输入为 bytes，先编码，然后生成盐和哈希，最后解码为字符串存储
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配
    :param plain_password: 用户输入的明文密码
    :param hashed_password: 数据库中存储的哈希密码
    :return: 匹配返回 True，否则返回 False
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

if __name__ == "__main__":
    # 这是一个辅助脚本，用于在初始化数据库时生成管理员密码的哈希值
    # 直接运行该文件：python utils/crypto.py
    import sys
    print("=== 密码哈希生成工具 ===")
    
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
    else:
        pwd = input("请输入要加密的明文密码 (例如 admin): ")
        
    if not pwd:
        print("密码不能为空！")
    else:
        hashed = get_password_hash(pwd)
        print(f"\n明文密码: {pwd}")
        print(f"哈希结果: {hashed}")
        print("\n请将上述哈希结果复制到数据库的 password 字段中。")