import asyncio
from app.core.cache import get_cache
from app.services import views

async def test():
    c = get_cache()
    key = await c.key('fundamentals', code='600745', days=90)
    print(f"缓存key: {key}")
    cached = await c.get_json(key)
    if cached:
        sectors = cached.get('sectors')
        print(f"缓存里的 sectors 类型: {type(sectors)}")
        print(f"缓存里的 sectors 长度: {len(sectors) if sectors else 0}")
        if sectors:
            print(f"第一个板块: {sectors[0]}")
    else:
        print("缓存未命中")

asyncio.run(test())
