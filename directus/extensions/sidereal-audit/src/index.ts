import { defineHook } from '@directus/extensions-sdk';

export default defineHook(({ action }, { logger }) => {
  action('generation_jobs.items.create', ({ payload }) => {
    const kind = (payload as Record<string, unknown>)['kind'];
    logger.info(`sidereal-audit: generation_jobs create kind=${typeof kind === 'string' ? kind : 'unknown'}`);
  });
});
