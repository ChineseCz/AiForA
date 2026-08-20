import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:/Users/HJF/PycharmProjec/PythonProject1/frontend/src/pages/StockDetail.tsx"
with open(path, encoding='utf-8') as f:
    src = f.read()

# ── Step 1: Remove the above-chart Collapse (基础指标+买点+卖点) ──
OLD_ABOVE = '''        <Collapse ghost size="small" style={{ marginBottom: 4 }} items={[
          ...SIGNAL_CATEGORIES.map((cat) => {
            const allChecked = cat.items.every((it) => signalVisibility[it.key]);
            const someChecked = cat.items.some((it) => signalVisibility[it.key]);
            return {
              key: cat.key,
              label: (
                <Checkbox
                  checked={allChecked}
                  indeterminate={!allChecked && someChecked}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => {
                    const next = e.target.checked;
                    setSignalVisibility((prev) => {
                      const v = { ...prev };
                      cat.items.forEach((it) => { v[it.key] = next; });
                      return v;
                    });
                  }}
                >
                  <Typography.Text strong style={{ fontSize: 12 }}>{cat.name}</Typography.Text>
                </Checkbox>
              ),
              children: (
                <Space wrap size={[12, 4]} style={{ marginLeft: 8 }}>
                  {cat.items.map((it) => (
                    <Checkbox
                      key={it.key}
                      checked={!!signalVisibility[it.key]}
                      onChange={(e) => setSignalVisibility((prev) => ({ ...prev, [it.key]: e.target.checked }))}
                    >
                      <span style={{ fontSize: 12 }}>
                        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: it.color, marginRight: 4 }} />
                        {it.name}
                      </span>
                    </Checkbox>
                  ))}
                </Space>
              ),
            };
          }),
        ]} />
        <Spin spinning={isLoading}>'''

if OLD_ABOVE not in src:
    print("ERROR: above-chart Collapse not found")
    sys.exit(1)

src = src.replace(OLD_ABOVE, '        <Spin spinning={isLoading}>', 1)

# ── Step 2: Insert buy/sell Collapse between InfoBar and chart div ──
OLD_INFOBAR = '              {active && <InfoBar bar={active} prevClose={prevClose} />}\n              <div style={{ position: "relative", marginTop: 8 }}>'

NEW_INFOBAR = '''              {active && <InfoBar bar={active} prevClose={prevClose} />}
              <Collapse ghost size="small" style={{ margin: "4px 0" }} items={[
                ...SIGNAL_CATEGORIES.filter((cat) => cat.key !== "basic").map((cat) => {
                  const allChecked = cat.items.every((it) => signalVisibility[it.key]);
                  const someChecked = cat.items.some((it) => signalVisibility[it.key]);
                  return {
                    key: cat.key,
                    label: (
                      <Checkbox
                        checked={allChecked}
                        indeterminate={!allChecked && someChecked}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => {
                          const next = e.target.checked;
                          setSignalVisibility((prev) => {
                            const v = { ...prev };
                            cat.items.forEach((it) => { v[it.key] = next; });
                            return v;
                          });
                        }}
                      >
                        <Typography.Text strong style={{ fontSize: 12 }}>{cat.name}</Typography.Text>
                      </Checkbox>
                    ),
                    children: (
                      <Space wrap size={[12, 4]} style={{ marginLeft: 8 }}>
                        {cat.items.map((it) => (
                          <Checkbox
                            key={it.key}
                            checked={!!signalVisibility[it.key]}
                            onChange={(e) => setSignalVisibility((prev) => ({ ...prev, [it.key]: e.target.checked }))}
                          >
                            <span style={{ fontSize: 12 }}>
                              <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: it.color, marginRight: 4 }} />
                              {it.name}
                            </span>
                          </Checkbox>
                        ))}
                      </Space>
                    ),
                  };
                }),
              ]} />
              <div style={{ position: "relative", marginTop: 8 }}>'''

if OLD_INFOBAR not in src:
    print("ERROR: InfoBar anchor not found")
    sys.exit(1)

src = src.replace(OLD_INFOBAR, NEW_INFOBAR, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print(f"Done. Lines: {len(src.splitlines())}")
