import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:/Users/HJF/PycharmProjec/PythonProject1/frontend/src/pages/StockDetail.tsx"
with open(path, encoding='utf-8') as f:
    src = f.read()

OLD = '''        <Collapse ghost size="small" style={{ marginTop: 4 }} items={[{
          key: "sv",
          label: <Space size={4}><EyeOutlined />信号显示</Space>,
          children: (
            <Space direction="vertical" size={10}>
              {SIGNAL_CATEGORIES.map((cat) => {
                const allChecked = cat.items.every((it) => signalVisibility[it.key]);
                const someChecked = cat.items.some((it) => signalVisibility[it.key]);
                return (
                  <div key={cat.key}>
                    <Checkbox
                      checked={allChecked}
                      indeterminate={!allChecked && someChecked}
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
                    <div style={{ marginLeft: 24, marginTop: 4 }}>
                      <Space wrap size={[12, 4]}>
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
                    </div>
                  </div>
                );
              })}
            </Space>
          ),
        }, {'''

NEW = '''        <Collapse ghost size="small" style={{ marginTop: 4 }} items={[
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
          {'''

if OLD not in src:
    print("ERROR: OLD block not found")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print("Done.")
print(f"New length: {len(src.splitlines())} lines")
