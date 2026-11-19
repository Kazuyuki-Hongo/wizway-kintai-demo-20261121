import { readFileSync } from 'node:fs';
import { test, expect, Locator, Page } from '@playwright/test';
import { getBaseUrl } from '../helpers/base-url';

function summaryBlock(summary: Locator, label: string) {
  return summary.locator('div').filter({ hasText: label }).locator('dd');
}

async function openDemo(page: Page) {
  const base = getBaseUrl();
  await page.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
}

async function loginAs(page: Page, name: string, password: string) {
  await page.getByLabel('社員名').selectOption(name);
  await page.getByLabel('パスワード').fill(password);
  await page.getByRole('button', { name: 'ログイン' }).click();
  await expect(page.getByText(`ログイン中: ${name}`)).toBeVisible();
}

/**
 * 勤怠デモ。ログインしてから一覧と保存を使う。保存は共有ファイルに残る。
 * ローカルは playwright.config の webServer が API + Vite を起動する。
 * デプロイ済みを見るときは PLAYWRIGHT_BASE_URL を設定する。
 */
test.describe('勤怠デモ', () => {
  test('aozoraでは全員の勤怠が出ず、自分の11月だけ出る', async ({ page }) => {
    await openDemo(page);

    await expect(page.getByRole('heading', { name: '勤怠デモ' })).toBeVisible();
    const passwords = page.getByRole('table', { name: 'デモ用のパスワード' });
    await expect(passwords.getByRole('row', { name: /テスト青空/ })).toContainText('aozora');
    await expect(passwords.getByRole('row', { name: /テスト青空/ })).toContainText('本人');
    await expect(passwords.getByRole('row', { name: /サンプル海原/ })).toContainText('unahara');
    await expect(passwords.getByRole('row', { name: /見本山辺/ })).toContainText('yamabe');
    const adminRow = passwords.getByRole('row', { name: /デモ管理/ });
    await expect(adminRow).toContainText('kanri');
    await expect(adminRow).toContainText('管理者');
    await expect(page.getByRole('cell', { name: '105' })).toHaveCount(0);

    await page.getByLabel('社員名').selectOption('テスト青空');
    await page.getByLabel('パスワード').fill('wrong');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.locator('p.error')).toContainText('社員名かパスワードが違います');
    await expect(page.getByRole('cell', { name: '105' })).toHaveCount(0);

    await loginAs(page, 'テスト青空', 'aozora');
    await expect(page.getByRole('button', { name: '自分の勤怠' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '全員の勤怠' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'この月をCSVで出す' })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: 'サンプル海原', exact: true })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: '見本山辺', exact: true })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: '120' })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: '112' })).toHaveCount(0);
    await expect(page.getByText('その場で入力できます')).toBeVisible();
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');
    await expect(page.getByRole('cell', { name: '2026-11-21', exact: true })).toBeVisible();
    await expect(page.getByLabel('2026-11-21 出勤')).toHaveValue('');
    await expect(page.getByLabel('2026-11-20 出勤')).toHaveValue('09:00');

    const summary = page.locator('dl.summary');
    await expect(summaryBlock(summary, '出勤日数')).toHaveText('14');
    await expect(summaryBlock(summary, '総実働（時間）')).toHaveText('105');
    await expect(summaryBlock(summary, '8時間超過（時間）')).toHaveText('1');
    await expect(summaryBlock(summary, '退勤なし件数')).toHaveText('1');
    await expect(page.getByLabel('2026-11-05 区分')).toHaveValue('欠勤');
    await expect(page.getByLabel('2026-11-07 出勤')).toHaveValue('');
    await expect(page.getByLabel('2026-11-08 出勤')).toHaveValue('');

    await page.getByRole('button', { name: 'ログアウト' }).click();
    await expect(page.getByRole('button', { name: 'ログイン' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '管理者', exact: true })).toBeVisible();
  });

  test('unaharaの直後は自分の11月2日だけで、全員の勤怠は無い', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'サンプル海原', 'unahara');
    await expect(page.getByRole('button', { name: '全員の勤怠' })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: 'テスト青空', exact: true })).toHaveCount(0);
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');
    const summary = page.locator('dl.summary');
    await expect(summaryBlock(summary, '出勤日数')).toHaveText('15');
    await expect(summaryBlock(summary, '総実働（時間）')).toHaveText('120');
  });

  test('退勤が出勤より前だと保存が拒否される', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await page.getByLabel('月').fill('2026-11');

    await page.getByLabel('2026-11-02 退勤').fill('08:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.locator('p.error')).toContainText('退勤は出勤より前にはできません');
    await expect(page.getByText('保存しました')).toHaveCount(0);
  });

  test('備考を保存すると再表示でも同じ文字列が出る', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'サンプル海原', 'unahara');
    await page.getByLabel('月').fill('2026-11');

    // 既存の保存済み日に備考だけ載せる（空日を新規出勤にすると共有 DB の合計が後続ケースと食い違う）
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await page.getByLabel('2026-11-02 備考').fill('客先A');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByText('保存しました')).toBeVisible();
    await expect(page.getByLabel('2026-11-02 備考')).toHaveValue('客先A');

    await page.getByRole('button', { name: 'ログアウト' }).click();
    await loginAs(page, 'サンプル海原', 'unahara');
    await page.getByLabel('月').fill('2026-11');
    await expect(page.getByLabel('2026-11-02 備考')).toHaveValue('客先A');
  });

  test('休憩を時刻のように入れると長さとして拒否される', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await page.getByLabel('月').fill('2026-11');

    const clockOut = page.getByLabel('2026-11-02 退勤');
    const before = await clockOut.inputValue();
    await page.getByLabel('2026-11-02 休憩').fill('12:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.locator('p.error')).toContainText('休憩は時刻ではなく長さです');
    await expect(clockOut).toHaveValue(before);
  });

  test('退勤の拒否が返るまで保存していますと出て、返ったあとは18:00のまま', async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    let hits = 0;
    await page.route('**/days/2026-11-02', async (route) => {
      if (route.request().method() !== 'PUT') {
        await route.continue();
        return;
      }
      hits += 1;
      await gate;
      await route.continue();
    });

    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await page.getByLabel('2026-11-02 退勤').fill('08:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByRole('button', { name: '保存しています' })).toBeVisible();
    await expect(page.getByText('保存しました')).toHaveCount(0);
    await page.getByRole('button', { name: '保存しています' }).click({ force: true });
    expect(hits).toBe(1);
    release();
    await expect(page.locator('p.error')).toContainText('退勤は出勤より前にはできません');
    await expect(page.getByText('保存しました')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '保存しています' })).toHaveCount(0);
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');
  });

  test('kanriは全員の勤怠から3人を開き、青空の保存はデモ管理として残る', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'デモ管理', 'kanri');
    await expect(page.getByRole('button', { name: '個別の勤怠' })).toBeVisible();
    await expect(page.getByRole('button', { name: '自分の勤怠' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '全員の勤怠' })).toBeVisible();
    await expect(page.getByLabel('社員').locator('option:checked')).toHaveText('テスト青空');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');
    await expect(summaryBlock(page.locator('dl.summary'), '出勤日数')).toHaveText('14');

    await page.getByRole('button', { name: '全員の勤怠' }).click();
    await expect(page.getByRole('button', { name: /を保存/ })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: 'テスト青空', exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'サンプル海原', exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: '見本山辺', exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'デモ管理', exact: true })).toHaveCount(0);
    await expect(page.getByRole('cell', { name: '105' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '120' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '112' })).toBeVisible();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'この月をCSVで出す' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('kintai-2026-11.csv');
    const csvPath = await download.path();
    expect(csvPath).toBeTruthy();
    const csv = readFileSync(csvPath as string, 'utf8');
    expect(csv).toContain('テスト青空');
    expect(csv).toContain('2026-11-02');
    expect(csv).not.toContain('デモ管理');

    await page.getByRole('row', { name: /サンプル海原/ }).getByRole('button', { name: '日ごとを入力' }).click();
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');

    await page.getByRole('button', { name: '全員の勤怠' }).click();
    await page.getByRole('row', { name: /テスト青空/ }).getByRole('button', { name: '日ごとを入力' }).click();
    await expect(summaryBlock(page.locator('dl.summary'), '出勤日数')).toHaveText('14');
    await page.getByLabel('2026-11-02 退勤').fill('19:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByText('保存しました')).toBeVisible();
    await expect(page.getByRole('row', { name: /2026-11-02/ })).toContainText('デモ管理');
    const summary = page.locator('dl.summary');
    await expect(summaryBlock(summary, '総実働（時間）')).toHaveText('106');
    await expect(summaryBlock(summary, '8時間超過（時間）')).toHaveText('2');
  });

  test('ログインと日ごとの読み込み中は待っていると出る', async ({ page }) => {
    let releaseLogin!: () => void;
    const loginGate = new Promise<void>((resolve) => {
      releaseLogin = resolve;
    });
    let loginHits = 0;
    await page.route('**/login', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      loginHits += 1;
      await loginGate;
      await route.continue();
    });
    let releaseMonth!: () => void;
    const monthGate = new Promise<void>((resolve) => {
      releaseMonth = resolve;
    });
    await page.route('**/employees/*/months/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      await monthGate;
      await route.continue();
    });

    await openDemo(page);
    await page.getByLabel('社員名').selectOption('サンプル海原');
    await page.getByLabel('パスワード').fill('unahara');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByRole('button', { name: 'ログインしています' })).toBeVisible();
    await page.getByRole('button', { name: 'ログインしています' }).click({ force: true });
    expect(loginHits).toBe(1);
    releaseLogin();
    await expect(page.getByText('ログイン中: サンプル海原')).toBeVisible();
    await expect(page.getByRole('button', { name: '自分の勤怠' })).toHaveCount(0);
    await expect(page.getByText('読み込んでいます')).toBeVisible();
    await expect(page.getByRole('button', { name: /を保存/ })).toHaveCount(0);
    releaseMonth();
    await expect(page.getByText('読み込んでいます')).toHaveCount(0);
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('18:00');
    await expect(page.getByRole('button', { name: '全員の勤怠' })).toHaveCount(0);
  });

  test('月を切り替えているあいだは前の日を保存できない', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'サンプル海原', 'unahara');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');

    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/employees/*/months/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      await gate;
      await route.continue();
    });
    await page.getByLabel('月').fill('2026-12');
    await expect(page.getByText('読み込んでいます')).toBeVisible();
    await expect(page.getByRole('button', { name: '2026-11-02 を保存' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '自分の勤怠' })).toHaveCount(0);
    await expect(page.getByText('ログイン中: サンプル海原')).toBeVisible();
    release();
    await expect(page.getByText('読み込んでいます')).toHaveCount(0);
    await expect(page.getByLabel('2026-12-02 出勤')).toHaveValue('');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveCount(0);
  });

  test('遅い月の応答は、いま選んでいる月の表を替えない', async ({ page }) => {
    const pending: Array<() => void> = [];
    await page.route('**/employees/*/months/**', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      await new Promise<void>((resolve) => {
        pending.push(resolve);
      });
      await route.continue();
    });

    await openDemo(page);
    await page.getByLabel('社員名').selectOption('サンプル海原');
    await page.getByLabel('パスワード').fill('unahara');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect.poll(() => pending.length).toBe(2);
    await page.getByLabel('月').fill('2026-12');
    await expect.poll(() => pending.length).toBe(4);
    const november = page.waitForResponse(
      (response) =>
        response.url().includes('/months/2026-11') &&
        !response.url().includes('/summary') &&
        response.request().method() === 'GET',
    );
    pending[0]();
    pending[1]();
    await november;
    await expect(page.getByLabel('月')).toHaveValue('2026-12');
    await expect(page.getByText('読み込んでいます')).toBeVisible();
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveCount(0);
    pending[2]();
    pending[3]();
    await expect(page.getByText('読み込んでいます')).toHaveCount(0);
    await expect(page.getByLabel('2026-12-02 出勤')).toHaveValue('');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveCount(0);
  });

  test('保存が返るまで保存していますと出て、成立すると19:00になる', async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    let hits = 0;
    await page.route('**/days/2026-11-02', async (route) => {
      if (route.request().method() !== 'PUT') {
        await route.continue();
        return;
      }
      hits += 1;
      await gate;
      await route.continue();
    });

    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');
    await page.getByLabel('2026-11-02 退勤').fill('19:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByRole('button', { name: '保存しています' })).toBeVisible();
    await expect(page.getByText('保存しました')).toHaveCount(0);
    await page.getByRole('button', { name: '保存しています' }).click({ force: true });
    expect(hits).toBe(1);
    release();
    await expect(page.getByText('保存しました')).toBeVisible();
    await expect(page.getByRole('button', { name: '保存しています' })).toHaveCount(0);
    await expect(page.getByLabel('2026-11-02 退勤')).toHaveValue('19:00');
  });

  test('CSVが届くまで出していますと出て、届いたファイル名は11月', async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    let hits = 0;
    await page.route('**/months/2026-11/export', async (route) => {
      hits += 1;
      await gate;
      await route.continue();
    });

    await openDemo(page);
    await loginAs(page, 'デモ管理', 'kanri');
    await page.getByRole('button', { name: '全員の勤怠' }).click();
    await expect(page.getByRole('cell', { name: 'テスト青空', exact: true })).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'この月をCSVで出す' }).click();
    await expect(page.getByRole('button', { name: '出しています' })).toBeVisible();
    await page.getByRole('button', { name: '出しています' }).click({ force: true });
    expect(hits).toBe(1);
    release();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('kintai-2026-11.csv');
    await expect(page.getByRole('button', { name: '出しています' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'この月をCSVで出す' })).toBeVisible();
  });

  test('保存中に12月へ変えても、後から返った11月は表を替えない', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('09:00');

    let releasePut!: () => void;
    const putGate = new Promise<void>((resolve) => {
      releasePut = resolve;
    });
    const novemberReload: Array<() => void> = [];
    await page.route('**/days/2026-11-02', async (route) => {
      if (route.request().method() !== 'PUT') {
        await route.continue();
        return;
      }
      await putGate;
      await route.continue();
    });
    await page.route('**/employees/*/months/**', async (route) => {
      const url = route.request().url();
      if (route.request().method() !== 'GET' || !url.includes('/months/2026-11')) {
        await route.continue();
        return;
      }
      await new Promise<void>((resolve) => {
        novemberReload.push(resolve);
      });
      await route.continue();
    });

    await page.getByLabel('2026-11-02 退勤').fill('19:00');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByRole('button', { name: '保存しています' })).toBeVisible();
    await page.getByLabel('月').fill('2026-12');
    await expect(page.getByLabel('2026-12-02 出勤')).toHaveValue('');
    releasePut();
    await expect.poll(() => novemberReload.length).toBe(2);
    novemberReload[0]();
    novemberReload[1]();
    await expect(page.getByLabel('月')).toHaveValue('2026-12');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveCount(0);
    await expect(page.getByLabel('2026-12-02 出勤')).toHaveValue('');
  });

  test('全員の勤怠が届くまで読み込んでいますと出る', async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/months/*/overview', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      await gate;
      await route.continue();
    });

    await openDemo(page);
    await loginAs(page, 'デモ管理', 'kanri');
    await page.getByRole('button', { name: '全員の勤怠' }).click();
    await expect(page.getByText('読み込んでいます')).toBeVisible();
    await expect(page.getByRole('button', { name: '全員の勤怠' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'テスト青空', exact: true })).toHaveCount(0);
    release();
    await expect(page.getByText('読み込んでいます')).toHaveCount(0);
    for (const name of ['テスト青空', 'サンプル海原', '見本山辺']) {
      const row = page.getByRole('row', { name: new RegExp(name) });
      await expect(row.getByRole('cell', { name, exact: true })).toBeVisible();
      await expect(row.getByRole('cell').nth(1)).toHaveText(/^\d+$/);
      await expect(row.getByRole('cell').nth(2)).toHaveText(/^\d+$/);
    }
  });

  test('有休にすると自分の出勤日数が減る', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await page.getByLabel('月').fill('2026-11');
    await page.getByLabel('2026-11-02 区分').selectOption('有休');
    await expect(page.getByLabel('2026-11-02 出勤')).toHaveValue('');
    await page.getByRole('button', { name: '2026-11-02 を保存' }).click();
    await expect(page.getByText('保存しました')).toBeVisible();
    const summary = page.locator('dl.summary');
    await expect(summaryBlock(summary, '出勤日数')).toHaveText('13');
  });

  // 録画確認用。意図的に失敗させる（確認後に削除する）
  test('わざと失敗して録画を残す', async ({ page }) => {
    await openDemo(page);
    await loginAs(page, 'テスト青空', 'aozora');
    await page.getByRole('button', { name: '未実装の機能を試す' }).click();
    await expect(page.getByRole('alert')).toContainText('この機能はまだ実装されていません');
    // 画面に未実装エラーが出ているのに、成功したと誤って断言する
    await expect(page.getByText('処理が完了しました')).toBeVisible();
  });

  // CloudWatch に DemoError の traceback を残す演習用。意図的に失敗させる
  test('わざと /demo/error を叩いて失敗する', async ({ page }) => {
    await openDemo(page);
    const loginResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        /\/login\/?$/.test(new URL(response.url()).pathname),
    );
    await loginAs(page, 'テスト青空', 'aozora');
    const loginResponse = await loginResponsePromise;
    const loginUrl = new URL(loginResponse.url());
    const apiBase = `${loginUrl.origin}${loginUrl.pathname.replace(/\/login\/?$/, '')}`;

    const errorUrl = `${apiBase}/demo/error?marker=training-e2e`;
    let status = 0;
    let body = '';
    try {
      const errorResponse = await page.request.get(errorUrl);
      status = errorResponse.status();
      body = await errorResponse.text();
    } catch (err) {
      // ローカル local_server は未処理 DemoError で接続を切ることがある（デプロイ先は 500）
      body = String(err);
    }
    // DemoError で 500（または接続切断）になる想定なのに、成功したと誤って断言する
    expect(
      status >= 200 && status < 300,
      `意図どおり DemoError 経路。status=${status} body=${body}`,
    ).toBe(true);
  });
});
