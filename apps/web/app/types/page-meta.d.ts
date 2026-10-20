declare module '#app' {
  interface PageMeta {
    /** Farm-app access: omitted = signed-in users only. */
    auth?: 'guest' | 'public'
  }
}

export {}
