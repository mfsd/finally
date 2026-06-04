import { expect, test } from '@playwright/test';

import { DEFAULT_TICKERS } from '../support/constants';
import {
  cashBalance,
  connectionStatus,
  expectIntegratedAppReady,
  gotoApp,
  tickerRow,
  waitForSsePriceEvents,
} from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('fresh start shows seeded watchlist, $10k cash, and streaming prices', async ({ page }) => {
  await gotoApp(page);

  await expect(cashBalance(page), 'fresh profile cash balance should be visible').toBeVisible();

  for (const ticker of DEFAULT_TICKERS) {
    await expect(tickerRow(page, ticker), `default watchlist should include ${ticker}`).toBeVisible();
  }

  await expect(connectionStatus(page), 'market stream connection indicator should be visible').toBeVisible();
  await waitForSsePriceEvents(page);
});
