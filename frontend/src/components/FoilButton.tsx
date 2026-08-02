/* Holographic-foil <button> wrapper (engine: lib/foil, hook: useFoil).
   Use this inside .map() or wherever a hook per button is awkward:

     <FoilButton className="btn" foil={{ shape: 'conic' }} onClick={...}>Approve</FoilButton>

   All button props (onClick, disabled, type, aria-*, …) pass through untouched. */

import { forwardRef, type ComponentPropsWithoutRef } from 'react'

import { type FoilOptions } from '../lib/foil'
import { useFoil } from './useFoil'

export interface FoilButtonProps extends ComponentPropsWithoutRef<'button'> {
  foil?: FoilOptions
}

/** A <button> with the foil effect attached. All button props pass through. */
export const FoilButton = forwardRef<HTMLButtonElement, FoilButtonProps>(
  function FoilButton({ foil, ...props }, forwardedRef) {
    const foilRef = useFoil<HTMLButtonElement>(foil)
    return (
      <button
        {...props}
        ref={(el) => {
          foilRef.current = el
          if (typeof forwardedRef === 'function') forwardedRef(el)
          else if (forwardedRef) forwardedRef.current = el
        }}
      />
    )
  },
)
