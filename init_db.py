"""数据库初始化脚本 - 2表设计"""
from loguru import logger
from app.database import engine, Base, SessionLocal
from app.models import LiveRoom, VideoSegment

def init_database():
    """初始化数据库表和默认配置"""
    logger.info("开始初始化数据库...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")
    
    # 2表设计，所有配置使用.env文件，无需插入默认配置
    logger.info("使用2表设计，配置从.env文件读取")
    
    logger.info("数据库初始化完成！")


if __name__ == "__main__":
    init_database()
