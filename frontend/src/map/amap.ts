import AMapLoader from '@amap/amap-jsapi-loader'
import { AMAP_LOAD_TIMEOUT_MS } from '../config/map'

let amapPromise: Promise<any> | null = null

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error('AMAP_LOAD_TIMEOUT')), timeoutMs)
    promise.then(
      (value) => {
        window.clearTimeout(timeout)
        resolve(value)
      },
      (error) => {
        window.clearTimeout(timeout)
        reject(error)
      },
    )
  })
}

export function loadAMap(): Promise<any> {
  if (amapPromise) return amapPromise
  const key = import.meta.env.VITE_AMAP_KEY
  const securityJsCode = import.meta.env.VITE_AMAP_SECURITY_JS_CODE
  if (!key) return Promise.reject(new Error('AMAP_KEY_MISSING'))
  if (!securityJsCode) return Promise.reject(new Error('AMAP_SECURITY_CODE_MISSING'))

  ;(window as unknown as { _AMapSecurityConfig: { securityJsCode: string } })._AMapSecurityConfig = { securityJsCode }
  amapPromise = withTimeout(
    AMapLoader.load({
      key,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar'],
    }),
    AMAP_LOAD_TIMEOUT_MS,
  ).catch((error) => {
    amapPromise = null
    throw error
  })
  return amapPromise
}

export function waitForMapReady(map: any): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false
    const complete = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      map.off('complete', complete)
      resolve()
    }
    const timeout = window.setTimeout(() => {
      if (settled) return
      settled = true
      map.off('complete', complete)
      reject(new Error('AMAP_INITIALIZATION_TIMEOUT'))
    }, AMAP_LOAD_TIMEOUT_MS)
    map.on('complete', complete)
  })
}
