import { expect, test } from '@playwright/test';

import { TRADE_TICKER } from '../support/constants';
import {
  cashBalance,
  expectIntegratedAppReady,
  gotoApp,
  positionRow,
  positionsTable,
  submitTrade,
} from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('buys and sells shares with portfolio state reflected in the UI', async ({ page }) => {
  await gotoApp(page);

  const initialCash = await cashBalance(page).first().textContent();

  await submitTrade(page, 'buy', TRADE_TICKER, '1');
  await expect(positionsTable(page), 'positions table should render after buying').toBeVisible();
  await expect(positionRow(page, TRADE_TICKER), `${TRADE_TICKER} position should appear after buy`).toBeVisible();
  await expect(cashBalance(page), 'cash balance should update after buy').not.toHaveText(initialCash ?? '');

  await submitTrade(page, 'sell', TRADE_TICKER, '1');
  await expect(positionRow(page, TRADE_TICKER), `${TRADE_TICKER} position should be closed or updated after sell`).toBeHidden();
});
