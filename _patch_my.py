import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:/Users/HJF/PycharmProjec/PythonProject1/frontend/src/pages/My.tsx"
with open(path, encoding='utf-8') as f:
    src = f.read()

# 1. Remove whiteSpace pre-wrap from preview container
src = src.replace('            whiteSpace: "pre-wrap",\n', '')

# 2. Replace old renderNoteContent function with two new functions
OLD_FUNC_START = "function renderNoteContent(\n  content: string,"
OLD_FUNC_END = "  if (last < content.length)\n    parts.push(<span key={`s${last}`}>{content.slice(last)}</span>);\n  return parts;\n}"

start_idx = src.find(OLD_FUNC_START)
end_str = OLD_FUNC_END
end_idx = src.find(end_str, start_idx)
if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found. start={start_idx}, end={end_idx}")
    sys.exit(1)

end_idx += len(end_str)

NEW_FUNCS = '''function renderBracketToken(key: string, inner: string, replaceAt: (s: string) => void): React.ReactNode {
  if (inner === "✓是") {
    return <span key={key} style={{ background: "#f6ffed", color: "#52c41a", border: "1px solid #b7eb8f", borderRadius: 4, padding: "0 6px", cursor: "pointer", fontSize: 12, margin: "0 2px" }} onClick={() => replaceAt("【是/否】")}>✓ 是</span>;
  }
  if (inner === "✗否") {
    return <span key={key} style={{ background: "#fff2f0", color: "#ff4d4f", border: "1px solid #ffccc7", borderRadius: 4, padding: "0 6px", cursor: "pointer", fontSize: 12, margin: "0 2px" }} onClick={() => replaceAt("【是/否】")}>✗ 否</span>;
  }
  if (inner.includes("/") || inner.includes("、")) {
    const sep = inner.includes("/") ? "/" : "、";
    const singleSelect = sep === "/";
    const opts = inner.split(sep);
    const handleClick = (oi: number) => {
      const isSel = opts[oi].startsWith("✓");
      const newOpts = opts.map((o, i) => {
        const clean = o.startsWith("✓") ? o.slice(1) : o;
        if (i !== oi) return singleSelect ? clean : o;
        return isSel ? clean : "✓" + clean;
      });
      replaceAt("【" + newOpts.join(sep) + "】");
    };
    return (
      <span key={key} style={{ display: "inline-flex", flexWrap: "wrap", gap: 2, margin: "0 2px" }}>
        {opts.map((opt, oi) => {
          const isSel = opt.startsWith("✓");
          const label = isSel ? opt.slice(1) : opt;
          return (
            <span key={oi} onClick={() => handleClick(oi)}
              style={{ background: isSel ? "#f6ffed" : "transparent", color: isSel ? "#52c41a" : "#595959", border: `1px solid ${isSel ? "#b7eb8f" : "#d9d9d9"}`, borderRadius: 4, padding: "0 5px", cursor: "pointer", fontSize: 12, whiteSpace: "nowrap" }}>
              {isSel ? "✓ " : ""}{label}
            </span>
          );
        })}
      </span>
    );
  }
  if (/^_+$/.test(inner) || inner.startsWith("~") || inner === "填写" || inner === "请填写" || inner === "输入") {
    const val = inner.startsWith("~") ? inner.slice(1) : "";
    return (
      <input key={key} type="text" value={val} placeholder="____"
        onChange={(e) => { const v = e.target.value; replaceAt(v ? "【~" + v + "】" : "【____】"); }}
        style={{ border: "none", borderBottom: "1px solid #aaa", background: "transparent", fontSize: 13, color: "inherit", outline: "none", padding: "0 2px", width: Math.max(40, val.length * 14 + 16) + "px" }}
      />
    );
  }
  return <span key={key} style={{ color: "#d48806", background: "#fffbe6", borderRadius: 3, padding: "0 3px", fontSize: 13 }}>{"【" + inner + "】"}</span>;
}

function renderNoteContent(
  content: string,
  onChange: (s: string) => void,
): React.ReactNode {
  const lines = content.split("\\n");
  return (
    <>
      {lines.map((line, li) => {
        let lineStart = 0;
        for (let i = 0; i < li; i++) lineStart += lines[i].length + 1;

        const hm = line.match(/^##\\s+(.+?)(?:\\s*\\((\\d{6})\\))?\\s*$/);
        if (hm) {
          const [, title, code] = hm;
          return (
            <div key={li} style={{ fontSize: 14, fontWeight: 600, marginTop: li > 0 ? 10 : 0, marginBottom: 2, borderLeft: "3px solid #1677ff", paddingLeft: 8 }}>
              {code ? <Link to={`/stock/${code}`} style={{ color: "inherit" }}>{title}({code})</Link> : title}
            </div>
          );
        }

        const parts: React.ReactNode[] = [];
        let last = 0;
        let ti = 0;
        let match: RegExpExecArray | null;
        const re = /【([^】]*)】|\\*\\*([^*\\n]+)\\*\\*|==([^=\\n]+)==/g;
        while ((match = re.exec(line)) !== null) {
          if (match.index > last)
            parts.push(<span key={`${li}_s${last}`}>{line.slice(last, match.index)}</span>);
          const absPos = lineStart + match.index;
          if (match[1] !== undefined) {
            const inner = match[1];
            const full = match[0];
            const replaceAt = (next: string) => onChange(content.slice(0, absPos) + next + content.slice(absPos + full.length));
            parts.push(renderBracketToken(`${li}_t${ti++}`, inner, replaceAt));
          } else if (match[2] !== undefined) {
            parts.push(<strong key={`${li}_b${ti++}`}>{match[2]}</strong>);
          } else {
            parts.push(<mark key={`${li}_m${ti++}`} style={{ background: "#fff3cd", color: "#d46b08", borderRadius: 2, padding: "0 2px" }}>{match[3]}</mark>);
          }
          last = re.lastIndex;
        }
        if (last < line.length)
          parts.push(<span key={`${li}_s${last}`}>{line.slice(last)}</span>);

        return <div key={li} style={{ minHeight: "1.4em" }}>{parts}</div>;
      })}
    </>
  );
}'''

src = src[:start_idx] + NEW_FUNCS + src[end_idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

print("Done. File written.")
print(f"New length: {len(src.splitlines())} lines")
