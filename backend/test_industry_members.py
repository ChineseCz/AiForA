from app.services.external import sina

# 测试行业板块成分股拉取
industry_code = "hangye_ZK70"  # 房地产业
print(f"测试行业板块成分股拉取: {industry_code}")

try:
    codes = sina.fetch_board_members(industry_code)
    print(f"返回结果: {len(codes)} 只股票")
    if codes:
        print(f"前5个: {codes[:5]}")
    else:
        print("❌ 返回空列表")
except Exception as e:
    print(f"❌ 异常: {e}")

# 对比概念板块
concept_code = "chgn_730610"  # 大健康
print(f"\n测试概念板块成分股拉取: {concept_code}")

try:
    codes = sina.fetch_board_members(concept_code)
    print(f"返回结果: {len(codes)} 只股票")
    if codes:
        print(f"前5个: {codes[:5]}")
except Exception as e:
    print(f"❌ 异常: {e}")
