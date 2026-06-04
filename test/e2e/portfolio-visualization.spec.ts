import { expect, test } from '@playwright/test';

import { VISUAL_TICKER } from '../support/constants';
import { expectIntegratedAppReady, gotoApp, positionRow, submitTrade } from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('portfolio heatmap and P&L chart render after a position exists', async ({ page }) => {
  await gotoApp(page);

  await submitTrade(page, 'buy', VISUAL_TICKER, '1');
  await expect(positionRow(page, VISUAL_TICKER)).toBeVisible();

  const heatmap = page.getByTestId('portfolio-heatmap');
  const pnlChart = page.getByTestId('chart-Portfolio P&L');

  await expect(heatmap, 'portfolio treemap/heatmap should be visible').toBeVisible();
  await expect(pnlChart, 'P&L chart should be visible').toBeVisible();

  await expect(heatmap.locator('canvas, svg').first(), 'heatmap should render a canvas or svg').toBeVisible();
  await expect(pnlChart.locator('canvas, svg').first(), 'P&L chart should render a canvas or svg').toBeVisible();
});
