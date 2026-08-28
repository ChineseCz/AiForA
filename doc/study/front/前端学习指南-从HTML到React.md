# 前端学习指南：从 HTML 到 React

## 1. 学习目标

本文帮助熟悉传统前端开发的人理解现代 React 前端，重点回答几个问题：

- 浏览器最终显示的页面是什么？
- HTML、CSS、JavaScript 各自负责什么？
- React 和传统前端有什么区别？
- TSX 是什么？它为什么看起来像 HTML？
- React 如何根据数据变化自动更新页面？
- 当前项目的前端代码应该如何阅读？

## 2. 浏览器最终显示的是什么

浏览器最终显示的是 DOM 页面。

HTML 是页面结构的文本描述，例如：

```html
<h1>雪球看板</h1>
<button>登录</button>
```

浏览器读取 HTML 后，会把它转换成 DOM，也就是内存中的页面节点结构：

```text
Document
  ├── h1：雪球看板
  └── button：登录
```

CSS 决定这些节点如何显示，JavaScript 可以读取和修改这些节点。

因此可以先记住：

```text
HTML：页面结构
CSS：页面样式
JavaScript：页面逻辑和交互
DOM：浏览器实际管理的页面结构
```

无论使用原生 JavaScript、Vue 还是 React，浏览器最后都要把内容变成 DOM 并显示出来。

### 2.1 React 项目为什么还保留 `index.html`

React 项目通常仍然保留一个很简单的 `index.html`，因为浏览器打开网址时首先需要加载一个 HTML 文档。它一般只提供应用启动外壳：

```html
<!doctype html>
<html>
  <head>
    <title>雪球看板</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

这个文件通常不直接写看板、选股或管理后台的业务内容。它主要负责：

- 提供浏览器加载页面的入口。
- 提供 React 挂载的位置，例如 `#root`。
- 加载 `main.tsx` 编译后的 JavaScript。
- 放置标题、图标、viewport 等基础页面信息。

之后 React 会执行类似下面的挂载逻辑：

```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
```

完整关系是：

```text
index.html：启动外壳和挂载点
  ↓
main.tsx：启动 React
  ↓
App.tsx：组织路由和全局布局
  ↓
pages/*.tsx：生成实际业务页面
```

所以用户最终看到的是 React 挂载到 `#root` 里的页面，而不是一个单独写满业务内容的 `index.html`。不过浏览器开发者工具中仍然可以看到最终生成的 HTML DOM。

## 3. 传统前端是怎么工作的

传统方式通常是 HTML、CSS 和 JavaScript 分开：

```html
<button id="btn">点击</button>
<p id="result">点击次数：0</p>
```

```css
button {
  color: white;
  background: blue;
}
```

```javascript
let count = 0;

document.querySelector("#btn").onclick = () => {
  count += 1;
  document.querySelector("#result").textContent = "点击次数：" + count;
};
```

传统 JavaScript 是命令式的。开发者需要明确告诉浏览器：

1. 找到哪个元素。
2. 监听什么事件。
3. 修改哪个属性或文字。
4. 哪些元素需要显示或隐藏。

页面规模较小时很直观，但页面复杂后，多个地方同时修改 DOM，容易出现状态不同步。

## 4. JavaScript 和页面结构有关吗

有关。JavaScript 可以通过 DOM API 修改页面结构：

```javascript
const title = document.createElement("h1");
title.textContent = "新的标题";
document.body.appendChild(title);
```

JavaScript 不只是计算数字，也可以：

- 创建 HTML 元素。
- 删除 HTML 元素。
- 修改文字和属性。
- 修改 CSS 类名。
- 监听点击、输入、滚动等事件。
- 根据接口返回的数据生成页面。

传统前端的主要问题不是 JavaScript 不能操作页面，而是大型页面中手动操作页面会变得难以维护。

## 5. React 改变了什么

React 没有抛弃 HTML，也没有替代浏览器。它改变的是页面代码的组织方式。

传统方式：

```text
先写页面
再手动查找元素
再手动修改元素
```

React 方式：

```text
用组件描述页面
用状态描述数据
状态变化后由 React 更新页面
```

例如：

```tsx
function LoginArea({ loggedIn }: { loggedIn: boolean }) {
  return loggedIn ? <button>退出登录</button> : <button>登录</button>;
}
```

这段代码表达的是：

```text
如果已登录，显示退出按钮；
否则显示登录按钮。
```

开发者描述“页面应该是什么样”，而不是手动描述“如何一步步修改 DOM”。这叫声明式 UI。

## 6. TSX 是什么

TSX 是 TypeScript 和 JSX 的结合。

```text
.html：HTML 文件
.ts：TypeScript 文件
.tsx：可以写 TypeScript 和 JSX 的 React 文件
```

示例：

```tsx
function Welcome({ name }: { name: string }) {
  return <h1>你好，{name}</h1>;
}
```

其中：

- `name: string` 是 TypeScript 类型。
- `<h1>你好，{name}</h1>` 是 JSX 页面结构。
- `Welcome` 是 React 组件。

TSX 不是浏览器直接执行的 HTML。Vite 会先编译 TSX，React 再把它转换成浏览器可以使用的 DOM。

大致过程是：

```text
TSX
  ↓ Vite/TypeScript 编译
JavaScript
  ↓ React 运行
浏览器 DOM
  ↓
用户看到的 HTML 页面
```

## 7. React 组件

React 页面由组件组成。组件通常是一个返回 JSX 的函数：

```tsx
function Header() {
  return <header>雪球看板</header>;
}
```

组件可以组合：

```tsx
function App() {
  return (
    <div>
      <Header />
      <main>页面内容</main>
    </div>
  );
}
```

可以把组件理解为可重复使用的页面零件：

```text
App
  ├── Header
  ├── Sidebar
  ├── Dashboard
  └── Footer
```

当前项目中：

```text
pages/*.tsx       页面级组件
components/*.tsx  可复用组件
App.tsx           应用外壳和路由
```

## 8. Props：组件的输入

组件可以通过 props 接收外部数据：

```tsx
function StockName({ name, code }: { name: string; code: string }) {
  return <span>{name}（{code}）</span>;
}
```

使用时：

```tsx
<StockName name="平安银行" code="000001" />
```

Props 类似函数参数：

```text
父组件提供数据
  ↓
子组件根据数据生成页面
```

通常子组件不直接修改 props，而是通过事件通知父组件。

## 9. State：页面会变化的数据

State 是组件自己管理的数据。最常见的写法是 `useState`：

```tsx
const [count, setCount] = useState(0);
```

它包含两部分：

```text
count：当前值
setCount：修改值的方法
```

例如：

```tsx
function Counter() {
  const [count, setCount] = useState(0);

  return (
    <button onClick={() => setCount(count + 1)}>
      点击次数：{count}
    </button>
  );
}
```

执行过程：

```text
初始 count = 0
  ↓ 点击
setCount(1)
  ↓
React 重新执行组件
  ↓
页面显示 count = 1
```

状态变化是 React 自动更新页面的核心。

## 10. React 如何更新页面

当组件第一次运行时，React 根据 JSX 生成页面。

```tsx
<p>点击次数：0</p>
```

状态变化后，组件生成新结果：

```tsx
<p>点击次数：1</p>
```

React 会比较前后的页面描述：

```text
标签没有变化
属性没有变化
只有文字从 0 变成 1
```

于是只更新需要改变的 DOM，而不是整个页面全部重建。这个过程叫协调或 Reconciliation。

入门阶段可以把它理解为：

```text
旧页面描述 + 新页面描述
  ↓ React 比较差异
只更新真正变化的部分
```

## 11. 事件处理

React 中事件写在 JSX 属性上：

```tsx
<button onClick={handleClick}>登录</button>
```

```tsx
function handleClick() {
  console.log("用户点击了登录");
}
```

常见事件包括：

```tsx
onClick
onChange
onSubmit
onFocus
onBlur
onKeyDown
```

表单示例：

```tsx
const [username, setUsername] = useState("");

<input
  value={username}
  onChange={(event) => setUsername(event.target.value)}
/>
```

这里输入框的内容由 React state 管理，这种方式叫受控组件。

## 12. 条件和循环渲染

条件渲染：

```tsx
{loggedIn ? <Admin /> : <Login />}
```

或者：

```tsx
{loading && <p>加载中...</p>}
```

列表渲染：

```tsx
{stocks.map((stock) => (
  <div key={stock.code}>{stock.name}</div>
))}
```

`key` 用于帮助 React 识别列表中的每个元素，通常使用稳定的数据库 ID 或代码。

## 13. useEffect：处理外部副作用

组件除了生成页面，还可能需要：

- 请求接口。
- 监听窗口变化。
- 注册事件。
- 初始化第三方图表。
- 页面卸载时清理资源。

这些行为通常使用 `useEffect`：

```tsx
useEffect(() => {
  window.addEventListener("resize", handleResize);

  return () => {
    window.removeEventListener("resize", handleResize);
  };
}, []);
```

`return` 中的函数是清理逻辑，组件卸载时执行。

## 14. 路由：单页应用如何切换页面

React 项目通常使用 React Router：

```tsx
<Route path="/screener" element={<Screener />} />
<Route path="/admin" element={<Admin />} />
```

访问不同路径时，React 显示不同组件：

```text
/screener -> Screener.tsx
/admin    -> Admin.tsx
/stock/xx -> StockDetail.tsx
```

浏览器不一定重新加载整个 HTML 文件，而是由 React 切换当前页面组件。

当前项目中，路由和全局布局主要在：

```text
frontend/src/App.tsx
```

## 15. 前端如何请求后端

传统 JavaScript 可以直接使用 `fetch`：

```javascript
fetch("/api/stocks")
  .then((response) => response.json())
  .then((data) => console.log(data));
```

当前项目使用 Axios 和 TanStack Query。

```text
页面
  ↓
api/hooks.ts
  ↓
api/client.ts
  ↓
HTTP /api/xxx
  ↓
FastAPI
```

`client.ts` 负责：

- 附加管理员或访客 JWT。
- 统一处理 401。
- 清理失效登录状态。
- 读取后端错误信息。

`hooks.ts` 负责：

- 封装查询接口。
- 缓存接口结果。
- 管理加载和错误状态。
- 封装新增、修改和删除操作。

## 16. TanStack Query 解决什么问题

如果每个页面都手动管理接口状态，通常要写：

```text
loading
error
data
重试
刷新
缓存
```

TanStack Query 把这些通用问题集中管理。

页面可以关注数据展示：

```tsx
const { data, isLoading, error } = useStocks();
```

然后根据状态显示：

```tsx
if (isLoading) return <Spin />;
if (error) return <Alert message="加载失败" />;
return <StockTable data={data} />;
```

## 17. 当前项目的前端文件如何对应

```text
frontend/src/main.tsx
  React 启动入口

frontend/src/App.tsx
  页面路由、整体布局、Header、导航

frontend/src/pages/*.tsx
  实际页面组件

frontend/src/components/*.tsx
  可复用页面组件

frontend/src/api/client.ts
  Axios、token、401 处理

frontend/src/api/hooks.ts
  接口请求 hooks

frontend/src/api/types.ts
  接口数据类型

frontend/src/auth.tsx
frontend/src/visitorAuth.tsx
  管理员和访客登录态

frontend/src/theme.tsx
  主题状态

frontend/src/index.css
  全局样式
```

例如管理后台退出入口的修复路径是：

```text
App.tsx
  全局 Header 账号菜单提供退出入口

Admin.tsx
  后台页面本身只负责后台内容，不重复提供退出按钮

auth.tsx
  真正清理管理员 token 和更新登录状态

api/client.ts
  请求中统一使用管理员 token
```

## 18. 建议的学习顺序

### 第一阶段：基础页面

学习：

- HTML 标签和页面结构
- CSS 选择器、盒模型、Flex、Grid
- JavaScript 变量、函数、对象、数组
- DOM 查询和事件监听

目标是能独立写出一个传统的登录页面或列表页面。

### 第二阶段：现代 JavaScript

学习：

- `let`、`const`
- 箭头函数
- `map`、`filter`、`find`
- 解构和展开运算符
- Promise 和 `async/await`
- `fetch` 或 Axios
- ES Module 的 `import/export`

目标是能调用后端接口并处理返回数据。

### 第三阶段：TypeScript

学习：

- 基本类型
- 数组和对象类型
- 函数参数和返回值
- interface 和 type
- 可选属性
- 联合类型
- 泛型的基本用法

目标是能看懂 `.ts` 和 `.tsx` 文件中的类型声明。

### 第四阶段：React 基础

学习：

- 组件
- JSX/TSX
- props
- state
- 事件处理
- 条件渲染
- 列表渲染
- `useEffect`
- `useMemo` 和 `useCallback` 的基本使用场景

目标是能写出一个包含表单、列表和状态切换的 React 页面。

### 第五阶段：项目级 React

学习：

- React Router
- Context
- TanStack Query
- 表单管理
- 权限路由
- 错误处理
- 组件拆分
- Vite 构建
- Docker + Nginx 部署

目标是能读懂并修改当前项目的前端代码。

## 19. 阅读现有页面的方法

建议以 `Admin.tsx` 或 `Dashboard.tsx` 为例，按以下顺序阅读：

1. 先看 import，确认它使用了哪些组件、hooks 和接口。
2. 找到 `export default function`，看页面入口。
3. 查看 `useState`，确认页面有哪些本地状态。
4. 查看自定义 hooks，确认页面请求了哪些后端数据。
5. 阅读 `return`，理解页面结构。
6. 找按钮的 `onClick`，理解用户操作。
7. 回到 `api/hooks.ts`，查看接口 URL。
8. 到后端 router 中寻找对应接口。

常见定位链路：

```text
页面显示问题
  -> pages/*.tsx
  -> components/*.tsx
  -> index.css

接口数据问题
  -> pages/*.tsx
  -> api/hooks.ts
  -> api/client.ts
  -> backend router

登录问题
  -> VisitorLogin.tsx
  -> auth.tsx / visitorAuth.tsx
  -> api/client.ts
  -> backend user_auth.py / deps.py
```

## 20. React 的优点和代价

优点：

- 组件可以复用。
- 页面逻辑和状态关系清晰。
- 状态变化后自动更新页面。
- 适合复杂的交互式应用。
- 生态成熟，第三方组件丰富。
- 可以使用 TypeScript 提前发现错误。

代价：

- 需要学习组件、状态、hooks 和路由。
- 通常需要 Vite 等构建工具。
- 项目依赖较多，初学时不如单个 HTML 文件直观。
- 出问题时需要同时检查组件、状态、接口和构建流程。
- 前端 JavaScript 体积可能比传统静态页面更大。

因此 React 不是所有页面的必需品。简单展示页可以使用 HTML、CSS 和少量 JavaScript；复杂的管理后台、行情看板、选股工具更适合使用 React。

## 21. 最终理解

可以用下面这句话概括：

> React 没有替代 HTML，而是把“手动修改 HTML 页面”变成了“用组件和状态描述页面，React 自动把变化同步到浏览器 DOM”。

当前项目的前端运行过程是：

```text
TSX 页面组件
  ↓
Vite 编译
  ↓
React 运行组件和状态
  ↓
React Router 切换页面
  ↓
TanStack Query 请求后端数据
  ↓
React 更新 DOM
  ↓
浏览器显示最终页面
```

**维护日期**：2026-08-24  
**适用分支**：`dev`
