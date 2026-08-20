import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:/Users/HJF/PycharmProjec/PythonProject1/frontend/src/pages/StockDetail.tsx"
with open(path, encoding='utf-8') as f:
    src = f.read()

# The signal-groups Collapse + sp Collapse (combined) currently sits after </Spin>.
# We need to split it: signal groups go BEFORE <Spin>, sp stays AFTER </Spin>.

SIGNAL_MAP_BLOCK = '''          ...SIGNAL_CATEGORIES.map((cat) => {
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

# The combined Collapse block starts here:
OLD_COLLAPSE = '        <Collapse ghost size="small" style={{ marginTop: 4 }} items={[\n' + SIGNAL_MAP_BLOCK

NEW_COLLAPSE_ABOVE = '''        <Collapse ghost size="small" style={{ marginBottom: 4 }} items={[
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

# The anchor we use: replace "</Spin>\n        <Collapse ... items={[\n...SIGNAL_MAP..."
# with: the signal Collapse above + Spin start, then the sp-only Collapse remains after </Spin>

OLD_ANCHOR = '        </Spin>\n' + OLD_COLLAPSE
NEW_ANCHOR = '        ' + NEW_COLLAPSE_ABOVE.split('\n        <Spin spinning={isLoading}>')[0].rstrip() + '\n'

# Simpler approach: find the </Spin> + full combined Collapse block and restructure it.
# Step 1: locate the spin closing + combined collapse start
SPIN_CLOSE = '        </Spin>\n        <Collapse ghost size="small" style={{ marginTop: 4 }} items={[\n          ...SIGNAL_CATEGORIES.map'

if SPIN_CLOSE not in src:
    print("ERROR: anchor not found")
    # Try to print surrounding text for debug
    idx = src.find('</Spin>')
    print(f"</Spin> found at index: {idx}")
    print(repr(src[idx:idx+200]))
    sys.exit(1)

# Replace: remove signal groups from after-spin Collapse, add them before Spin
BEFORE_SPIN = '''        <Collapse ghost size="small" style={{ marginBottom: 4 }} items={[
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
        </Spin>
        <Collapse ghost size="small" style={{ marginTop: 4 }} items={[{'''

src = src.replace(SPIN_CLOSE, BEFORE_SPIN, 1)

# Now find where we inserted BEFORE_SPIN and also move the Collapse block BEFORE <Spin>
# The structure is now: <Card><Spin>...chart...</Spin><Collapse(signal)></Collapse(sp)></Card>
# But we want: <Card><Collapse(signal)><Spin>...chart...</Spin><Collapse(sp)></Card>

# Find the Spin start inside Card and move BEFORE_SPIN block before it
SPIN_OPEN = '        <Spin spinning={isLoading}>\n'
SIG_COLLAPSE_START = '        <Collapse ghost size="small" style={{ marginBottom: 4 }}'

spin_idx = src.find(SPIN_OPEN)
sig_idx = src.find(SIG_COLLAPSE_START)

if spin_idx == -1 or sig_idx == -1:
    print(f"ERROR: spin_idx={spin_idx}, sig_idx={sig_idx}")
    sys.exit(1)

if sig_idx > spin_idx:
    # Signal Collapse is after Spin close — need to move it before Spin open
    # Find where the signal Collapse ends (closes with ]} />)
    close_marker = '        ]} />\n        </Spin>'
    close_idx = src.find(close_marker, sig_idx)
    if close_idx == -1:
        print("ERROR: close_marker not found")
        print(repr(src[sig_idx:sig_idx+300]))
        sys.exit(1)

    # Extract the signal Collapse block
    sig_block_end = close_idx + len('        ]} />\n')
    sig_block = src[sig_idx:sig_block_end]

    # Remove it from current position, insert before Spin
    src_without = src[:sig_idx] + src[sig_block_end:]
    # Now find Spin open in the modified source
    spin_idx2 = src_without.find(SPIN_OPEN)
    src = src_without[:spin_idx2] + sig_block + src_without[spin_idx2:]
    print("Moved signal Collapse before Spin")
else:
    print("Signal Collapse is already before Spin - no move needed")

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print(f"Done. New length: {len(src.splitlines())} lines")
