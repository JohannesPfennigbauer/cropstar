export default defineNuxtConfig({
  modules: ['@nuxt/ui', '@nuxt/eslint', '@nuxtjs/i18n'],
  devtools: { enabled: true },

  app: {
    head: {
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }]
    }
  },
  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // Override with NUXT_PUBLIC_CONTACT_EMAIL / NUXT_PUBLIC_REPOSITORY_URL.
      contactEmail: 'hello@cropstar.at',
      repositoryUrl: 'https://github.com/JohannesPfennigbauer/cropstar',
      // Needed for hreflang and canonical links; set NUXT_PUBLIC_I18N_BASE_URL in production.
      i18n: {
        baseUrl: 'http://localhost:3000'
      }
    }
  },

  // Marketing and teaching pages are static HTML; the farm app (Stage 3) is client-only.
  routeRules: {
    '/': { prerender: true },
    '/en': { prerender: true },
    '/app/**': { ssr: false }
  },
  compatibilityDate: '2025-07-15',

  nitro: {
    preset: 'node-server'
  },

  typescript: {
    strict: true,
    typeCheck: false
  },
  telemetry: false,

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never'
      }
    }
  },

  i18n: {
    defaultLocale: 'de',
    strategy: 'prefix_except_default',
    locales: [
      { code: 'de', language: 'de-AT', name: 'Deutsch', file: 'de.json' },
      { code: 'en', language: 'en', name: 'English', file: 'en.json' }
    ],
    // German stays the default; visitors switch deliberately rather than by browser header.
    detectBrowserLanguage: false
  }
})
