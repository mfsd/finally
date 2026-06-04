import { expect, test } from '@playwright/test';

import { expectIntegratedAppReady, gotoApp } from '../support/app';

test.beforeEach(async ({ request, baseURL }) => {
  await expectIntegratedAppReady(request, baseURL);
});

test('AI chat returns a response in the panel', async ({ page }) => {
  await gotoApp(page);

  const input = page.getByTestId('chat-input');
  await input.fill('Analyze my portfolio in one short sentence. Do not trade.');
  await expect(input).toHaveValue('Analyze my portfolio in one short sentence. Do not trade.');
  const chatResponse = page.waitForResponse((response) => response.url().includes('/api/chat') && response.ok());
  await page.getByTestId('chat-send-button').click();
  const response = await chatResponse;
  const payload = await response.json();
  expect(payload.message, 'chat API should return assistant text').toEqual(expect.any(String));
  expect(payload.message.length, 'assistant response should not be empty').toBeGreaterThan(0);

  const chat = page.getByTestId('ai-chat');
  await expect(chat, 'chat panel should be visible').toBeVisible();
  await expect(chat.getByText(payload.message), 'assistant response should appear').toBeVisible();
});
