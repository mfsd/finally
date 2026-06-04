import { expect, test } from '@playwright/test';

import { TEST_TICKER } from '../support/constants';
import { addTicker, expectIntegratedAppReady, gotoApp, removeTicker, tickerRow } from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('adds and removes a ticker from the watchlist', async ({ page }) => {
  await gotoApp(page);

  await addTicker(page, TEST_TICKER);
  await expect(tickerRow(page, TEST_TICKER), `${TEST_TICKER} should appear after adding`).toBeVisible();

  await removeTicker(page, TEST_TICKER);
  await expect(tickerRow(page, TEST_TICKER), `${TEST_TICKER} should disappear after removing`).toBeHidden();
});
