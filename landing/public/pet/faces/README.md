Sushi-kun's face expressions — overlaid on/composited with the sushi-eaten
body art in `public/pet/sushi/`, displayed above the caption in
`components/SushiDemo.tsx`.

Drop the 9 images here as:

    face-01.png
    face-02.png
    face-03.png
    face-04.png
    face-05.png
    face-06.png
    face-07.png
    face-08.png
    face-09.png

Wiring TODO (not done yet): decide the face-to-state mapping (moods are
currently just happy/worried/sick/dying/graduated — 5 values — so 9 faces
covers more granularity than `Mood` alone, e.g. transient expressions like
"just healed" or "just spoke"). Once the mapping is decided, extend
`lib/petModel.ts` with a `face` field alongside `mood` in `PetSnapshot`.
