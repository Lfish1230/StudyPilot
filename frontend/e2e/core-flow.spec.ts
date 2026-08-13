import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.join(currentDirectory, "artifacts", "tcp-course-notes.pdf");
const screenshotDirectory = path.resolve(currentDirectory, "../../docs/screenshots");

test.beforeAll(async ({ browser }) => {
  await mkdir(path.dirname(fixturePath), { recursive: true });
  const page = await browser.newPage();
  await page.setContent(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <style>body{font-family:Arial,"Microsoft YaHei",sans-serif;padding:72px;line-height:1.8;color:#162236}h1{color:#315c9c}</style>
    </head><body><h1>计算机网络课程笔记：TCP 连接基础</h1>
    <p>TCP 是面向连接的传输层协议。建立连接时，客户端与服务端通常执行三次握手。</p>
    <p>三次握手用于确认通信双方的发送能力和接收能力，并同步建立可靠连接所需的初始序列信息。</p>
    <p>本测试资料由 StudyPilot 项目原创，以 CC0 1.0 许可发布，仅用于自动化演示。</p>
    </body></html>`);
  await page.pdf({ path: fixturePath, format: "A4", printBackground: true });
  await page.close();
});

test("student completes the grounded learning flow", async ({ page }) => {
  test.setTimeout(90_000);
  const unique = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
  const email = `e2e-${unique}@example.com`;
  const password = "e2e-secure-password";

  await page.goto("/register");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "注册" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByRole("heading", { name: "我的课程" })).toBeVisible();

  await page.getByLabel("新课程名称").fill("计算机网络");
  await page.getByRole("button", { name: "创建课程" }).click();
  await expect(
    page.getByRole("heading", { name: "计算机网络" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "进入课程" }).click();
  await page.getByRole("link", { name: "资料" }).click();

  await page.getByLabel("选择 PDF 文件").setInputFiles(fixturePath);
  await expect(page.getByText("tcp-course-notes.pdf")).toBeVisible();
  await expect(page.getByText("可用", { exact: true })).toBeVisible({ timeout: 30_000 });

  await page.getByRole("link", { name: "问答" }).click();
  await page.getByLabel("向课程资料提问").fill("TCP 为什么需要三次握手？");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText(/确认双方的发送与接收能力/)).toBeVisible();
  await page.getByRole("button", { name: "查看引用 1" }).click();
  await expect(page.getByRole("dialog")).toContainText("第 1 页");
  await page.getByRole("button", { name: "关闭引用" }).click();

  if (process.env.UPDATE_SCREENSHOTS === "1") {
    await mkdir(screenshotDirectory, { recursive: true });
    await page.locator(".account-actions span").evaluate((element) => {
      element.textContent = "demo@studypilot.dev";
    });
    await page.screenshot({
      path: path.join(screenshotDirectory, "course-workspace.png"),
      fullPage: false,
    });
  }

  await page.getByRole("link", { name: "测验", exact: true }).click();
  await page.getByRole("checkbox", { name: /tcp-course-notes.pdf/ }).check();
  await page.getByLabel("选择题").fill("2");
  await page.getByLabel("简答题").fill("0");
  await page.getByRole("button", { name: "生成测验" }).click();
  await expect(page.getByRole("heading", { name: "TCP 连接基础测验" })).toBeVisible();

  await page.getByLabel("三次", { exact: true }).check();
  await page.getByLabel("确认双方收发能力并同步连接信息").check();
  await page.getByRole("button", { name: "提交测验" }).click();
  await expect(page.getByLabel("得分 100%")).toBeVisible();

  if (process.env.UPDATE_SCREENSHOTS === "1") {
    await page.locator(".account-actions span").evaluate((element) => {
      element.textContent = "demo@studypilot.dev";
    });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.locator(".result-summary p").last().evaluate((element) => {
      element.textContent = "已完成 · 2026/8/13 20:00:00";
    });
    await page.screenshot({
      path: path.join(screenshotDirectory, "quiz-result.png"),
      fullPage: false,
    });
  }

  await page.getByRole("link", { name: "分析" }).click();
  await expect(page.getByText("测验次数").locator("..")).toContainText("1");
  await expect(page.getByText("平均得分").locator("..")).toContainText("100%");
});
