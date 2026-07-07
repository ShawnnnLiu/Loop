# Mobile Engineer (iOS/Android) — Track Profile

**Proposed enum value:** `mobile_engineer` · **Wave 2** · Research
grounded 2026-07-06.

## Track decision

**The marginal case in the granularity policy — resolved as: own track
that heavily reuses the `swe` base.** Evidence both ways:

- *Specialization evidence:* big tech titles it "Software Engineer, iOS"
  and runs the same loop shape (DSA coding at LeetCode medium-hard +
  behavioral + design); startups are drifting native → cross-platform
  (https://newsletter.pragmaticengineer.com/p/native-vs-cross-platform).
- *Own-track evidence:* the **mobile system design round is materially
  different** — app-focused, not backend-focused, with its own canonical
  community framework (offline-first, pagination, caching, battery, push —
  https://github.com/weeeBox/mobile-system-design), and domain deep-dives
  probe platform internals (ARC, Swift 6 strict concurrency, Compose
  recomposition) that generalist SWE prep never touches. ~50% of the skill
  list is platform-specific.

Under the policy ("own track when loop stages differ materially"), the
distinct design round + platform deep-dive rounds justify the track. The
implementation is cheap in the right way: the DSA/git/testing foundation
arrives as track-tag additions to existing `swe` entries, so the track is
mostly overlay. Folding mobile entirely into `swe` would leave a 6–12-week
mobile prep plan unable to schedule its distinctive content.

**Resolver markers** (insert before `swe` — "mobile software engineer"
contains "software"): `"mobile engineer"`, `"mobile developer"`,
`"ios engineer"`, `"ios developer"`, `"android engineer"`,
`"android developer"`, `"react native"`, `"flutter developer"`.

One track for both platforms: postings and loops are platform-specific,
but the prep *shape* is identical and the shared overlay (mobile system
design, offline/caching, release management) is the same vocabulary.
iOS-vs-Android is a within-track choice the plan content handles, not an
enum distinction. Revisit if enrichment shows the corpora diverging hard.

## Role snapshot

Mature specialization; smaller than web (single-digit % of Stack Overflow
respondents vs 31% full-stack) but deep, liquid demand; 1k+ US "mobile
software engineer" LinkedIn postings. Prep is highly codified: SWE prep
plus a mobile overlay with its own canonical free framework.

## Prep-process profile

- **Interview loop** (Apple/Meta/Google archetype): recruiter → 1–2
  technical screens (coding + domain) → onsite 5–6 rounds: DSA coding (in
  Swift/Kotlin, platform-flavored follow-ups), **mobile system design**
  ("design an iOS chat app": View→Network→Storage layering, protocol
  tradeoffs REST/GraphQL/WebSocket, offline-first + conflict resolution,
  pagination, battery), platform deep-dive (ARC/GCD/actors; coroutines/
  Compose), behavioral
  (https://prepfully.com/interview-guides/ios-engineer).
- **Anchor resources:** weeeBox mobile-system-design repo (THE canonical
  framework); Hacking with Swift 150+ questions + career guide; Kodeco
  iOS-interview guides; anandwana001/android-interview bank; LeetCode for
  the DSA substrate.
- **Typical arc (6–12 weeks for mid-level):** DSA in Swift/Kotlin →
  platform fundamentals (ARC, concurrency, lifecycle, SwiftUI/Compose) →
  mobile-system-design exercises from the framework → mocks + behavioral.

## Seed skill entries (draft)

### Existing entries — add `mobile_engineer` tag (~15)

`skill.swift`, `skill.kotlin`, `skill.java` (legacy Android),
`skill.typescript` (RN), `skill.data-structures`, `skill.algorithms`,
`skill.dynamic-programming` (secondary), `skill.git`, `skill.testing`,
`skill.code-review`, `skill.debugging`, `skill.concurrency` (consider
adding aliases `gcd`, `grand central dispatch`), `skill.caching`,
`skill.rest-apis`, `skill.graphql`, `skill.websockets`, `skill.grpc`
(secondary), `skill.ci-cd`, `skill.sqlite`, `skill.system-design`
(generic fundamentals still asked).

### New entries

| skill_id | display_name | aliases | kind | tracks | note |
|---|---|---|---|---|---|
| `skill.swiftui` | SwiftUI | `swiftui` | framework | mobile_engineer | Default iOS UI expectation |
| `skill.uikit` | UIKit | `uikit` | framework | mobile_engineer | Dominant in existing codebases; both tested |
| `skill.swift-concurrency` | Swift Concurrency | `swift concurrency`, `swift actors` | framework | mobile_engineer | Swift 6 strict concurrency actively probed; bare `async/await` left out (language-generic) |
| `skill.core-data` | Core Data / SwiftData | `core data`, `swiftdata` | framework | mobile_engineer | iOS persistence standard |
| `skill.jetpack-compose` | Jetpack Compose | `jetpack compose` | framework | mobile_engineer | Bare `compose` left out — collides with docker-compose prose |
| `skill.kotlin-coroutines` | Kotlin Coroutines & Flow | `kotlin coroutines`, `coroutines`, `kotlin flow`, `stateflow` | framework | mobile_engineer | Heavily interviewed |
| `skill.android-jetpack` | Android Jetpack | `android jetpack`, `jetpack`, `viewmodel`, `livedata`, `workmanager` | framework | mobile_engineer | Architecture-components suite |
| `skill.room` | Room | `room database`, `room db` | framework | mobile_engineer | Bare `room` left out (common English); résumé surfaces usually say "Room database" — verify against eval fixtures |
| `skill.retrofit` | Retrofit / OkHttp | `retrofit`, `okhttp` | framework | mobile_engineer | Android networking standard |
| `skill.urlsession` | URLSession / Alamofire | `urlsession`, `alamofire` | framework | mobile_engineer | iOS networking standard |
| `skill.hilt` | Dagger / Hilt | `dagger`, `hilt` | framework | mobile_engineer | Android DI standard |
| `skill.react-native` | React Native | `react native` | framework | mobile_engineer | Cross-platform option in ~half of postings |
| `skill.flutter` | Flutter | `flutter`, `dart` | framework | mobile_engineer | Folding the Dart language in is a curation call |
| `skill.kmp` | Kotlin Multiplatform | `kotlin multiplatform`, `kmp`, `kmm` | framework | mobile_engineer | Adoption 7%→18% 2024→25; secondary |
| `skill.objective-c` | Objective-C | `objective-c`, `objc`, `obj-c` | language | mobile_engineer | Legacy iOS; secondary |
| `skill.xcode` | Xcode | `xcode` | tool | mobile_engineer | The iOS IDE |
| `skill.android-studio` | Android Studio | `android studio` | tool | mobile_engineer | The Android IDE |
| `skill.gradle` | Gradle | `gradle` | tool | mobile_engineer | Android build system |
| `skill.spm-cocoapods` | Swift Package Manager / CocoaPods | `swift package manager`, `spm`, `cocoapods` | tool | mobile_engineer | iOS dependency management |
| `skill.firebase` | Firebase | `firebase`, `crashlytics` | tool | mobile_engineer | Ubiquitous backend/crash suite |
| `skill.mobile-system-design` | Mobile System Design | `mobile system design`, `client architecture`, `app architecture` | concept | mobile_engineer | The distinctive interview round |
| `skill.memory-management` | Memory Management (ARC) | `memory management`, `arc`, `retain cycles`, `weak references` | concept | mobile_engineer | Signature iOS topic; `arc` is a noisy short token — trust long aliases |
| `skill.app-architecture` | App Architecture Patterns | `mvvm`, `mvi`, `viper`, `clean architecture`, `mvc` | concept | mobile_engineer | Architecture-decision questions; `mvc` arguably swe-shared — curation call |
| `skill.offline-first` | Offline-First & Sync | `offline-first`, `offline support`, `conflict resolution` | concept | mobile_engineer | Core design-round topic |
| `skill.app-lifecycle` | App Lifecycle | `app lifecycle`, `activity lifecycle`, `background execution` | concept | mobile_engineer | Baseline posting requirement |
| `skill.push-notifications` | Push & Deep Linking | `push notifications`, `apns`, `fcm`, `deep linking`, `universal links` | concept | mobile_engineer | Standard platform integration |
| `skill.pagination` | Pagination | `pagination`, `cursor pagination` | concept | mobile_engineer | Design-round staple; arguably swe-shared — curation call |
| `skill.app-store-release` | App Store Release Management | `app store connect`, `testflight`, `google play console`, `play console`, `phased rollout` | practice | mobile_engineer | Store-release cadence is mobile-specific; policy questions appear in interviews |
| `skill.mobile-testing` | Mobile Testing | `xctest`, `xcuitest`, `espresso` | practice | mobile_engineer | Explicit posting requirement; bare `junit` left out (Java-generic) |
| `skill.mobile-performance` | Mobile Performance & Battery | `app startup time`, `battery optimization`, `app size` | practice | mobile_engineer | Deep-dive content; secondary |
| `skill.fastlane` | Fastlane | `fastlane` | tool | mobile_engineer | Named mobile CI tool; secondary |

Shared NEW entries from other profiles that tag `mobile_engineer`:
`skill.platform-guidelines` (ux-designer.md), `skill.accessibility`
(secondary tag — voiceover/talkback), `skill.deployment-strategies`
(secondary — feature flags/phased rollout overlap; curation call on which
entry owns `feature flags`: recommendation is devops keeps it).

**Optional / deferred:** Combine, Instruments/profilers, Charles Proxy,
mobile security (keychain/keystore), Bitrise, app-store-optimization,
localization/i18n.

## Alias-collision & FTS5 notes

- `swift` (existing entry, also an English word *and* a payments network)
  and `dart` (a game, a verb) are among the noisiest aliases in the whole
  taxonomy — FTS counts for them are unusable; enrich via `swiftui`,
  `xcode`, `flutter` instead.
- Deliberately excluded aliases and why: `async/await` (JS/Python/C#
  generic), `compose` (docker compose), `room` (English), `junit`
  (Java-generic), `sync` (generic).
- `mvc`/`mvvm` are short but distinctive — good signals.
- This track has the highest count of NEW entries after security (~30) —
  the per-track budget lands around 50 total with the swe reuse, fine
  against the ~100 cap.

## Candidate corpus sources (manifest seeds)

| URL | expected type | note |
|---|---|---|
| https://github.com/weeeBox/mobile-system-design | role_taxonomy | THE canonical design-round framework; check repo license |
| https://github.com/SwiftAnytime/Mobile-System-Design-Interview-Guide | role_taxonomy | Complementary HLD/LLD breakdown |
| https://github.com/anandwana001/android-interview | role_taxonomy | Android question bank; community-maintained |
| https://www.hackingwithswift.com/interview-questions | role_taxonomy | 150+ curated iOS questions; © Paul Hudson — link, don't republish |
| https://www.hackingwithswift.com/career-guide | role_taxonomy | iOS career-path taxonomy |
| https://www.kodeco.com/10625296-navigating-the-ios-interview | role_taxonomy | iOS process guide; parts subscription-gated |
| https://prepfully.com/interview-guides/ios-engineer | role_taxonomy | Loop-stage taxonomy incl. the design round |
| https://www.gethireready.com/interview-guides/software-engineer-apple | interview_report | Apple loop anatomy |
| https://thenewstack.io/how-to-prepare-for-big-tech-interviews-as-an-ios-engineer/ | role_taxonomy | Practitioner prep guide; stable editorial site |
| https://medium.com/@jain.ayusch10/the-mobile-system-design-interview-my-faang-prep-journey-free-practice-resource-96afce1f9583 | interview_postmortem | First-person FAANG mobile prep; Medium metered |
| https://newsletter.pragmaticengineer.com/p/native-vs-cross-platform | company_engineering_blog | Native-vs-cross-platform hiring-shift analysis; partially paywalled |
| https://developer.android.com/guide | role_taxonomy | Official docs — **CC-BY-4.0, the best-licensed source in the mobile list** |
| https://developer.apple.com/documentation/ | role_taxonomy | Ground truth for iOS; license permits linking, restricts reproduction |

## Enrichment expectations

`swiftui`, `jetpack compose`, `kotlin`, `react native`, `flutter`,
`mobile system design` should register strongly (developer.android.com
alone will drive Jetpack-family counts). `swift` counts: ignore (noise).
`kmp`/`kotlin multiplatform` low counts expected — young; keep.

## Overlap with existing tracks

vs `swe`: ~50% shared by design (the track *is* swe-plus-overlay; the DSA
substrate arrives as track tags). vs `ux_designer`: platform guidelines +
accessibility. vs everything else: minimal.
