# Git 工作流说明

> 本文档记录项目的分支策略、提交规范和操作流程。

---

## 分支结构

```
master        ← release_v1 旧架构（Flask+SQLite），已归档，不再维护
release_v1    ← 同上，历史保留
release_v2    ← v2 早期分支，已被 dev 取代，可删除

dev           ← 当前主干（release_v2 架构），所有功能最终合入这里
  ↑
  ├── feature/xxx     功能开发分支（从 dev 拉出，完成后 PR → dev）
  └── fix/xxx         修复分支（安全修复/紧急 bug，从 dev 拉出，优先合入 dev）
```

### 各分支职责

| 分支 | 用途 | 可直接 push？ |
|---|---|---|
| `dev` | 集成主干，始终保持可部署状态 | 否，通过 merge 进入 |
| `feature/*` | 功能开发，一个 Phase 一个分支 | 是（自己的分支） |
| `fix/*` | 安全修复 / 紧急缺陷，需快速上线 | 是（自己的分支） |
| `master` | v1 旧架构，已归档 | 否 |

---

## 提交信息规范（Conventional Commits）

```
<type>(<scope>): <subject>

<body>  ← 可选，多行，说明 what/why
```

### type 类型

| type | 场景 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复（含安全修复） |
| `docs` | 文档变更 |
| `refactor` | 重构，不改变外部行为 |
| `perf` | 性能优化 |
| `chore` | 构建脚本、依赖升级等 |

### 示例

```
feat(phase10): 移动端UI适配 + 帖子brief摘要

fix(security): SEC-001~010 应用安全加固

docs: Phase9 访客账号系统交付报告
```

---

## 功能开发流程

```bash
# 1. 从 dev 拉功能分支
git checkout dev
git pull origin dev
git checkout -b feature/phase11-xxx

# 2. 开发、提交
git add <files>
git commit -m "feat(phase11): ..."

# 3. 开发完成，合回 dev
git checkout dev
git merge --no-ff feature/phase11-xxx -m "Merge feature/phase11-xxx into dev"
# 或者直接 fast-forward（无 merge commit，历史更线性）：
git merge --ff-only feature/phase11-xxx
```

---

## 安全修复 / 紧急 Bug 流程

**原则：安全修复不应被功能分支的未完成工作阻塞，需单独分支快速上线。**

```bash
# 1. 从 dev 当前最新 commit 拉修复分支（不是从 master！dev 才是主干）
git checkout dev
git checkout -b fix/security-hardening

# 2. 修复代码，独立提交（安全 commit 与功能 commit 严格分开）
git add <只 stage 安全相关文件>
git commit -m "fix(security): SEC-001 OTP 改用密码学安全随机数 ..."

# 3. 合入 dev（fast-forward 保持历史线性）
git checkout dev
git merge --ff-only fix/security-hardening

# 4. 如果功能分支（feature/*）也需要这个修复，cherry-pick 过去
git checkout feature/phase10-xxx
git cherry-pick <security-commit-hash>
```

### ⚠️ 注意：不要从 master 拉安全修复分支

本项目 master 是 release_v1 旧架构，与当前 dev 的 release_v2 代码完全不同。
安全修复分支**必须基于 dev**，否则 cherry-pick 会出现 modify/delete 冲突。

---

## 混合改动的处理（功能 + 安全改动在同一文件）

当一次工作同时涉及功能代码和安全修复，且修改了同一个文件时：

**拆成两个独立 commit，不要混在一起。**

```bash
# 方法：先 stage 安全相关文件，提交安全 commit；
#       再 stage 功能文件，提交功能 commit。

# 安全 commit（仅 stage 安全文件）
git add backend/app/core/security.py \
        backend/app/core/config.py \
        backend/app/api/deps.py \
        ...
git commit -m "fix(security): ..."

# 功能 commit（stage 剩余文件）
git add backend/app/models/ frontend/ ...
git commit -m "feat(phase10): ..."
```

如果同一个文件里既有功能改动又有安全改动（hunk 级别混合），用 `git add -p` 按块选择：

```bash
git add -p backend/app/repositories/posts.py
# 交互式选择：y=stage 这个 hunk，n=跳过，s=拆分更小粒度
```

---

## 历史操作记录

### 2026-07-13：安全加固 + 工作流规范化

**背景**：对 release_v2 架构（`dev` 分支）做全量安全评审，发现10项漏洞，同步修复。

**操作流程**：

```
# 初始状态（feature/mobile-ui-polish 有未提交的功能 + 安全改动混合）

1. 在 feature/mobile-ui-polish 拆成两个 commit：
   b79338c  fix(security): SEC-001~010 应用安全加固   ← 仅安全文件
   88e0c9f  feat(phase10): 移动端UI适配 + 帖子brief摘要 ← 功能文件

2. 从 dev 的最新 commit（87909fa）拉出安全修复分支：
   git checkout -b fix/security-hardening 87909fa

3. cherry-pick 安全 commit：
   git cherry-pick b79338c
   → 5d14ce2  fix(security): SEC-001~010 应用安全加固

4. 安全分支 fast-forward 合入 dev：
   git checkout dev
   git merge --ff-only fix/security-hardening
```

**最终分支状态**：

```
dev                   5d14ce2  安全修复已合入，可部署
fix/security-hardening 5d14ce2  同上（可删除）
feature/mobile-ui-polish 88e0c9f Phase10 功能，待后续合入 dev
release_v2            5a05c6a  Phase8 时代，已落后 dev，待删除
master/release_v1              v1 旧架构，归档
```

**踩坑记录**：第一次误从 master 拉 fix/security-hardening，cherry-pick 时全部冲突（modify/delete）。原因：master 是 v1 架构，没有 backend/app/ 目录，release_v2 的任何文件在 master 里都不存在。**正确做法：始终从 dev 拉修复分支。**

---

## 清理建议

```bash
# release_v2 已被 dev 取代，可删除本地和远端
git branch -d release_v2
git push origin --delete release_v2

# 已合入 dev 的安全修复分支
git branch -d fix/security-hardening

# master/release_v1 保留为历史归档，不操作
```
