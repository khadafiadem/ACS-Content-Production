# TikTok Content Posting — Audit Use Case

## Data aplikasi

- **App name:** App konten dekstop
- **App ID:** 7684154418485102612
- **Client Key:** `sbawp2ci2p83aj9q1o`
- **Client Secret:** `5Od7dOnsfepgsxitbxdo5Nw0xfAx1w9G`

> JANGAN tertukar dengan app "Aplikasi penjadwalan & publish otomatis konten" (App ID 7681859117614417941).

---

## Form Audit

**Video Content Category:** Health / Health and Fitness

**Use case description (English — salin langsung):**

> This application is an automated content production and scheduling system built for Apotek Cipta Sehat, a licensed Indonesian community pharmacy (Apotek). It generates short-form educational health videos (60–90 seconds, vertical 9:16) in the Indonesian language covering everyday wellness topics such as nutrition, sleep hygiene, work stress, hydration, and safe medication awareness.
>
> Every video starts with an engaging hook and ends with a clear disclaimer that the content is general health education and NOT a substitute for professional medical advice. Videos are created by our own team and AI-assisted copy, reviewed by staff before publishing, and do not contain copyrighted material, music, or third-party clips.
>
> The application uses the TikTok Content Posting API only to publish the videos we produce to our own account. We will post content that complies with TikTok's Community Guidelines and advertising policies, and each post links back to our pharmacy's official contact for further questions.
>
> We are requesting production access so we can schedule and auto-publish original, non-commercial, educational health content for our followers.

**Deskripsi (Bahasa Indonesia, opsional kalau form terima Bahasa Indonesia):**

> Aplikasi ini adalah sistem produksi dan penjadwalan konten otomatis milik Apotek Cipta Sehat, apotek berlisensi di Indonesia. Sistem membuat video edukasi kesehatan singkat (60–90 detik, vertikal 9:16) dalam Bahasa Indonesia dengan topik umum seperti nutrisi, kualitas tidur, stres kerja, hidrasi, dan kewaspadaan penggunaan obat.
>
> Setiap video diawali hook yang menarik dan ditutup disclaimer bahwa konten hanya edukasi umum dan bukan pengganti nasihat medis profesional. Konten dibuat oleh tim kami dibantu AI lalu direview staf sebelum dipublikasikan, tanpa materi berhak cipta, musik, atau klip pihak ketiga.
>
> API Content Posting TikTok hanya dipakai untuk memublikasikan video yang kami buat ke akun kami sendiri, sesuai Community Guidelines TikTok. Kami mohon akses produksi agar konten edukasi kesehatan yang orisinal dan non-komersial bisa terjadwal otomatis.

---

## Checklist sebelum submit

- [ ] Client Key di portal = `sbawp2ci2p83aj9q1o` (buka app "App konten dekstop" → tab Key & Secrets)
- [ ] Siapkan 2–3 contoh video (data/videos/content_*.mp4) untuk dilampirkan bila diminta
- [ ] Aktifkan scopes: `user.info.basic`, `video.publish`, `video.upload` (sudah ada di token)
- [ ] Pastikan `.env`: `AUTO_PUBLISH_PUBLIC=true`