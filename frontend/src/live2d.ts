// 菲比的 Live2D 形象：全局单例加载器。oh-my-live2d 会把舞台/画布挂到 document.body 上
// （不受 React 树控制），所以只应该在整个 App 生命周期里 loadOml2d 一次——用模块级变量
// 缓存实例和加载中的 Promise，避免 React StrictMode 开发环境下 effect 双调用导致挂两份。
import type { Oml2dEvents, Oml2dMethods, Oml2dProperties, Options } from "oh-my-live2d";

type Oml2dInstance = Oml2dProperties & Oml2dMethods & Oml2dEvents;

let instance: Oml2dInstance | null = null;
let loading: Promise<Oml2dInstance> | null = null;
// 菜单点击回调在 loadOml2d 调用那一刻就固定死了（往后不会再变），但触发聊天窗口要用的是
// React 组件当前这次渲染的 setOpen——用一个可被反复覆盖的间接层，组件每次挂载时更新它指向谁。
let openHandler: () => void = () => {};
export function setFeibiOpenHandler(fn: () => void) {
  openHandler = fn;
}
// 换形象的并发闩：loadNextModel() 是异步的，连点会并发触发好几次内部状态互相踩。
// 加个超时兜底——万一某次切换本身卡住/内部抛错没走到 finally，别让按钮从此永久失效。
let switching = false;
function guardedSwitch(next: () => Promise<void>) {
  if (switching) return;
  switching = true;
  const timeout = window.setTimeout(() => { switching = false; }, 8000);
  next().catch((e) => console.error("菲比换形象失败", e)).finally(() => {
    window.clearTimeout(timeout);
    switching = false;
  });
}

/** 拿已经加载好的实例；聊天窗口开合时用来控制形象滑入/滑出，没加载完就是 no-op（还没轮到形象出场）。 */
export function getFeibiInstance(): Oml2dInstance | null {
  return instance;
}

// oh-my-live2d 切模型时（models.js 的 clearAppStage）只把上一个模型从 PIXI 舞台上摘掉
// （removeChildren），从没调用过 pixi-live2d-display 模型自己的 .destroy()——纹理占的
// WebGL 资源就一直攥在手里不放。连着切了 5 次积压 5 个模型的贴图不释放，WebGL 上下文的纹理槃
// 用满后再加载新模型就直接失败，且卡死在失败状态（这就是"切到第6个必定报错"的真正原因，
// 不是某个模型文件坏了——8 个模型的文件我都逐个校验过是完整的）。这不是我们代码能避免的用法
// 问题，是库自己的资源释放漏了；打不了 node_modules 的补丁（下次 npm install 就没了），
// 所以在切换前，从实例上够到当前挂着的 pixi 模型对象，手动调用其 destroy() 抢救一下。
// oh-my-live2d 没把这个内部对象放进公开类型里，只能用 any 硬取。
function destroyCurrentPixiModel() {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const anyInst = instance as any;
    const model = anyInst?.models?.model;
    model?.destroy?.({ children: true, texture: true, baseTexture: true });
  } catch (e) {
    console.error("菲比：释放上一个模型资源失败（不影响继续切换）", e);
  }
}

export function ensureFeibiLive2d(): Promise<Oml2dInstance> {
  if (instance) return Promise.resolve(instance);
  if (loading) return loading;
  loading = import("oh-my-live2d").then(({ loadOml2d }) => {
    const options: Options = {
      dockedPosition: "right", // 侧栏导航在左边，菲比停靠在右下角别挡着
      sayHello: false,
      transitionTime: 600,
      primaryColor: "#1668dc",
      // 8 个模型都是 Live2D 官方仓库（Live2D/CubismWebSamples）的免费示例，下载到本地自己托管。
      // scale/position 先统一给个大致合理的默认值，没法在这边直接预览调——真机效果不对的话
      // 再按具体模型微调这两个数字。
      models: [
        { name: "hiyori", path: "/live2d/Hiyori/Hiyori.model3.json" },
        { name: "haru", path: "/live2d/Haru/Haru.model3.json" },
        { name: "mao", path: "/live2d/Mao/Mao.model3.json" },
        { name: "mark", path: "/live2d/Mark/Mark.model3.json" },
        { name: "natori", path: "/live2d/Natori/Natori.model3.json" },
        { name: "ren", path: "/live2d/Ren/Ren.model3.json" },
        { name: "rice", path: "/live2d/Rice/Rice.model3.json" },
        { name: "wanko", path: "/live2d/Wanko/Wanko.model3.json" },
      ].map((m) => ({
        ...m,
        scale: 0.09,
        position: [20, 20] as [number, number],
        stageStyle: { height: 300 },
        mobileScale: 0.07,
        mobileStageStyle: { height: 220 },
      })),
      tips: {
        idleTips: {
          message: [
            "有什么想问的都可以点我聊聊哦～",
            "站长辛苦啦，需要我帮忙看看系统情况吗？",
            "戳一下菜单里的对话按钮就能找我啦！",
          ],
          interval: 20000,
        },
        welcomeTips: { message: { daybreak: "早呀～我是菲比，管理后台的小助手！" } },
      },
      menus: {
        // icon 只能用组件内置图标 id（内部引用一份注入好的 iconfont sprite，不支持传外部图标 URL）
        items: [
          { id: "chat", icon: "icon-like", title: "找菲比聊聊", onClick: () => openHandler() },
          {
            id: "switch", icon: "icon-switch", title: "换个形象",
            onClick: (o) => guardedSwitch(async () => {
              destroyCurrentPixiModel();
              await o.loadNextModel();
            }),
          },
          // 收回：菜单本身挂在舞台元素内部，会跟着 stageSlideOut 一起滑出去，之后点不到——
          // 借用库自带的"休息条"（平时用于模型休眠提示）当召回入口，它是挂在 statusBar 独立
          // 元素上的，不受舞台滑出影响，点一下就 slideIn 召回。
          {
            id: "rest", icon: "icon-rest", title: "收起菲比",
            onClick: (o) => {
              o.stageSlideOut();
              o.statusBarOpen("菲比在这儿，点我召回～");
              o.setStatusBarClickEvent(() => {
                o.stageSlideIn();
                o.statusBarClose();
              });
            },
          },
        ],
      },
    };
    instance = loadOml2d(options);
    return instance;
  });
  return loading;
}
