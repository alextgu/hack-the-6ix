Sushi-kun's "eaten" stages — physical-health art, replaces the 🍣 emoji
placeholder in `components/SushiDemo.tsx`.

Drop the 6 images here as:

    sushi-0.png   (full, untouched — best physical)
    sushi-1.png
    sushi-2.png
    sushi-3.png
    sushi-4.png
    sushi-5.png   (fully eaten — worst physical)

Wiring TODO (not done yet): map `stateAtWeek().physical` (0-100) into a
0-5 bucket and swap the `<span>🍣</span>` in `SushiDemo.tsx` for
`<img src={`/pet/sushi/sushi-${bucket}.png`} />`, keeping the existing
`MOOD_SUSHI_STYLE` filter/transform for the mood-based animation on top.
