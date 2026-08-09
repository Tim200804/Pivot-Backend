"""Seed realistic message histories for Pivot demo."""
import sys
sys.path.insert(0, '.')

from models import get_user_by_id, create_message, list_conversation


# ── Helper: only insert if conversation is empty (idempotent) ──
def seed_conversation(sender_id, recipient_id, messages: list[tuple]):
    """messages: list of (sender_id, body_or_tuple) where tuple is (body, subject, alert_level, alert_type)"""
    existing = list_conversation(sender_id, recipient_id)
    if existing:
        print(f'  Skipping conversation {sender_id}↔{recipient_id} ({len(existing)} msgs exist)')
        return
    for item in messages:
        sid, *rest = item
        if len(rest) == 1:
            create_message(sid, recipient_id if sid == sender_id else sender_id, rest[0])
        elif len(rest) == 4:
            create_message(sid, recipient_id if sid == sender_id else sender_id, rest[0], rest[1], rest[2], rest[3])
        else:
            create_message(sid, recipient_id if sid == sender_id else sender_id, rest[0], rest[1])
    print(f'  Seeded conversation {sender_id}↔{recipient_id}: {len(messages)} msgs')


# ── ID mappings (from database) ──
# Athletes
ATH_TEST = 1        # test@upenn.edu - Test User
ATH_TIM = 2         # tim2008041227@gmail.com - tim
ATH_QQ = 3          # tim200823@qq.com - 1
ATH_TEST2 = 4       # test1785661442N@gmail.com - Test
ATH_2 = 6           # 2 - Test Athlete 2

# Coaches
COACH_TIM = 5       # 110098488@qq.com - tim (Head Coach)
COACH_ASSISTANT = 7 # assistant@pivot.dev - Assistant Coach
COACH_HEAD = 8      # head@pivot.dev - Head Coach
COACH_STRENGTH = 9  # strength@pivot.dev - Strength Coach
COACH_PSYCH = 10    # psych@pivot.dev - Sports Psych
COACH_TRAINER = 11  # trainer@pivot.dev - Athletic Trainer
COACH_ANALYST = 12  # analyst@pivot.dev - Performance Analyst


print("🌱 Seeding realistic message histories...")

# ── Coach Tim ↔ Athlete tim (bidirectional chat) ──
seed_conversation(COACH_TIM, ATH_TIM, [
    (COACH_TIM, "Hi tim, I noticed your HRV dropped 12% this week. How are you feeling?"),
    (ATH_TIM, "Hey coach. Yeah I've been sleeping poorly — exams coming up. Pushing through."),
    (COACH_TIM, "Understood. Let's reduce Thursday's erg session from 18k to 12k. Recovery first."),
    (ATH_TIM, "Thanks, that helps. I'll make sure to get 8 hours tonight."),
    (COACH_TIM, "Great. Also, the team nutritionist suggested more carbs before AM practice. Try it."),
    (ATH_TIM, "Will do. Toast before 6am rowing it is 🍞"),
    (COACH_TIM, "Haha exactly. I'll check your numbers Friday."),
])

# ── Head Coach → Athlete Test User (alert + follow-up) ──
seed_conversation(COACH_HEAD, ATH_TEST, [
    (COACH_HEAD, "Morgan, your resting HR has been trending up for 3 days (62→71 bpm). Any illness or unusual stress?",
     "⚠️ Elevated Resting HR Alert", "warning", "Heart Rate"),
    (ATH_TEST, "Nothing major — just some midterm stress. But I'll keep an eye on it."),
    (COACH_HEAD, "Ok. Let's flag it. Take tomorrow off from erg work. Light stretch only."),
    (ATH_TEST, "Got it. I'll rest and hydrate."),
])

# ── Assistant Coach ↔ Athlete Test 2 (check-in) ──
seed_conversation(COACH_ASSISTANT, ATH_TEST2, [
    (COACH_ASSISTANT, "Hey Sarah, just checking in. Your 2k split has improved 3 seconds since last month. Nice work!"),
    (ATH_TEST2, "Thank you! I've been adding morning yoga — seems to help my flexibility."),
    (COACH_ASSISTANT, "The data shows it. Keep it up. Don't forget: hydration goal is 3L on heavy training days."),
    (ATH_TEST2, "Noted! I'll set a reminder on my phone."),
])

# ── Coach Tim ↔ Athlete QQ (urgent alert) ──
seed_conversation(COACH_TIM, ATH_QQ, [
    (COACH_TIM, "URGENT: Your sleep score has been under 40 for 4 consecutive nights. This is a red alert.",
     "🔴 URGENT: Sleep Deficiency Critical", "critical", "Sleep"),
    (ATH_TIM, "(This is tim's coach responding) I'll make sure he sees this today."),
    (ATH_QQ, "Sorry coach. Been gaming late. I'll cut it off by 10pm from now on."),
    (COACH_TIM, "Appreciate the honesty. We'll re-evaluate your sleep data next Monday. Zero screens after 10pm."),
])

# ── Coach ↔ Coach: Head Coach notifies team about athlete crisis ──
seed_conversation(COACH_HEAD, COACH_ASSISTANT, [
    (COACH_HEAD, "FYI: Morgan (Test User) showed BLACK alert today — heart rate + sleep both critical. All coaches stay aware.",
     "URGENT: Morgan Smith — Crisis Alert", "black", "Multi-System Crisis"),
    (COACH_ASSISTANT, "On it. I'll pull her training log and review recent workloads."),
    (COACH_HEAD, "Good. Strength coach also notified. Let's meet after practice tomorrow."),
])

seed_conversation(COACH_HEAD, COACH_STRENGTH, [
    (COACH_HEAD, "Morgan's data is critical — may need to modify her strength plan this week. Can you review?",
     "⚠️ Morgan Smith — Modify Strength Plan", "black", "Multi-System Crisis"),
    (COACH_STRENGTH, "Agreed. I'll drop her squat volume by 30% and add mobility work instead."),
])

# ── Psych Coach ↔ Athlete Test (wellbeing check) ──
seed_conversation(COACH_PSYCH, ATH_TEST, [
    (COACH_PSYCH, "Hi Morgan. Your team mentioned you might benefit from a mental skills session. Want to chat?"),
    (ATH_TEST, "That would be great. Pre-race anxiety has been rough lately."),
    (COACH_PSYCH, "Let's schedule 20min this Friday. I'll send you a breathing exercise to try before then."),
])

# ── Strength Coach ↔ Athlete tim ──
seed_conversation(COACH_STRENGTH, ATH_TIM, [
    (COACH_STRENGTH, "Tim, your squat progression is solid. Add 5kg next week and keep the 3x5 rep scheme."),
    (ATH_TIM, "Copy that. Should I keep the accessory work the same?"),
    (COACH_STRENGTH, "Yes — lunges and core stability stay. Drop the plyos this week for recovery."),
])

# ── Analyst Coach → Head Coach (data insights) ──
seed_conversation(COACH_ANALYST, COACH_HEAD, [
    (COACH_ANALYST, "Weekly performance review: Sarah +3%, Tim -2%, Morgan -8% (but flagged for recovery). Full report attached.",
     "📊 Weekly Performance Metrics", "info", "Performance"),
    (COACH_HEAD, "Thanks. Morgan's -8% aligns with what we're seeing. Let's revisit after her recovery week."),
])

# ── Trainer ↔ Athlete Test 2 ──
seed_conversation(COACH_TRAINER, ATH_TEST2, [
    (COACH_TRAINER, "Sarah, you reported left shoulder tightness after yesterday's session. Still sore today?"),
    (ATH_TEST2, "A bit better. I did the mobility routine you gave me. Think I can erg today?"),
    (COACH_TRAINER, "Yes, but at 70% effort. Stop immediately if you feel sharp pain. I'll check on you during practice."),
])

print("\n✅ All seed messages created!")
