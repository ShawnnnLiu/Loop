/* React hook binding for the holographic foil effect (lib/foil).
   One line on any existing button:

     <button className="btn" ref={useFoil()} onClick={...}>Approve</button>
     <button className="btn" ref={useFoil({ shape: 'bar', palette: 'gold' })}>…</button>

   Inside .map() or when a ref is already in use, reach for <FoilButton>
   (components/FoilButton) instead — hooks can't be called in loops. */

import { useEffect, useRef, type MutableRefObject } from 'react'

import { registerFoil, type FoilOptions } from '../lib/foil'

/** Attach the foil effect to one element; pass the returned ref to it. */
export function useFoil<T extends HTMLElement = HTMLButtonElement>(
  options?: FoilOptions,
): MutableRefObject<T | null> {
  const ref = useRef<T | null>(null)
  // Options are plain data; keying the effect on their JSON keeps inline
  // object literals from re-registering every render.
  const optionsKey = JSON.stringify(options ?? {})
  useEffect(() => {
    const el = ref.current
    if (!el) return
    return registerFoil(el, JSON.parse(optionsKey) as FoilOptions)
  }, [optionsKey])
  return ref
}
