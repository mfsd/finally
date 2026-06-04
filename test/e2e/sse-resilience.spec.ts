import { expect, test } from '@playwright/test';

import { connectionStatus, expectIntegratedAppReady, gotoApp, waitForSsePriceEvents } from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('price stream can reconnect after a transient SSE failure', async ({ context, page }) => {
  await gotoApp(page);
  await waitForSsePriceEvents(page);

  await context.route('**/api/stream/prices', (route) => route.abort('connectionreset'));
  await page.reload();

  await expect(
    connectionStatus(page),
    'connection status should remain visible while the stream is reconnecting or disconnected',
  ).toBeVisible();

  await context.unroute('**/api/stream/prices');
  await page.reload();

  await expect(connectionStatus(page), 'connection status should recover after SSE is available again').toBeVisible();
  await waitForSsePriceEvents(page);
});
