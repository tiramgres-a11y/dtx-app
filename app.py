import streamlit as st
import anthropic

# ---------- Page config ----------
st.set_page_config(
    page_title="Genesis Team - מנהל סושיאל",
    page_icon="🏗️",
    layout="wide",
)

# ---------- Custom CSS for RTL + styling ----------
st.markdown(
    """
    <style>
    /* RTL for the whole app */
    .stApp, .stMarkdown, .stTextArea textarea,
    .stTextInput input, .stButton button {
        direction: rtl;
        text-align: right;
    }
    /* Make post cards look nice */
    .post-card {
        background-color: #f8f9fa;
        border-right: 4px solid #1a73e8;
        border-radius: 8px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        white-space: pre-wrap;
        line-height: 1.8;
        font-size: 1.05rem;
    }
    .post-title {
        font-weight: 700;
        font-size: 1.15rem;
        margin-bottom: 0.5rem;
        color: #1a73e8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ הגדרות")
    api_key = st.text_input(
        "הכנס מפתח API של Anthropic",
        type="password",
        placeholder="sk-ant-...",
    )
    st.divider()
    st.markdown("**דרישות:**")
    st.markdown("```\npip install streamlit anthropic\n```")

# ---------- Main area ----------
st.title("🏗️ הסוכן החכם של Genesis Team - מנהל סושיאל")
st.markdown("כתיבת פוסטים מקצועיים לפייסבוק עבור Genesis Team – יזמות נדל״ן והתחדשות עירונית.")
st.divider()

topic = st.text_area(
    "נושא הפוסט, נקודות מרכזיות או טקסט מכתבה רלוונטית",
    height=180,
    placeholder="לדוגמה: השקת פרויקט פינוי-בינוי חדש ברחוב הרצל 50, פתח תקווה. 120 יח״ד, מועד אכלוס משוער 2028...",
)

generate = st.button("🚀 צור פוסטים לפייסבוק", use_container_width=True)

# ---------- System prompt ----------
SYSTEM_PROMPT = (
    "אתה מנהל השיווק הדיגיטלי של Genesis Team, חברה מובילה ליזמות נדל\"ן "
    "והתחדשות עירונית. קהל היעד שלך הוא בעלי דירות בפרויקטים של פינוי-בינוי "
    "ותמ\"א, ומשקיעי נדל\"ן. טון הדיבור שלך הוא מקצועי, אמין, שקוף ונוסך "
    "ביטחון, אך נגיש ולא משפטי מדי. "
    "חוקי ברזל חמורים: "
    "1. הקפד על עברית תקנית ומושלמת. אסור להמציא פעלים או לתרגם סלנג לועזי מילולית. "
    "2. השתמש במושגים המקובלים בשוק הנדל\"ן הישראלי בלבד. "
    "3. חובה להשתמש תמיד באיות המדויק Genesis Team (למשל בהאשטאג #GenesisTeam). "
    "4. איסור מוחלט על שימוש באימוג'י. הפוסטים חייבים להיות טקסטואליים ונקיים לחלוטין."
)

USER_PROMPT_TEMPLATE = """בהתבסס על הנושא / הטקסט הבא, צור 3 חלופות שונות לפוסט בפייסבוק.

--- נושא / טקסט ---
{topic}
--- סוף הטקסט ---

הנחיות ליצירת החלופות:

**חלופה 1 – קצרה, חדה וקולעת (עד 4 שורות):**
נועדה לתפוס את העין של מי שגולל מהר בפיד. ללא סלנג מתורגם וללא אימוג'י.

**חלופה 2 – אינפורמטיבית ומעמיקה:**
פוסט שמסביר תהליך, ערך או יתרון בצורה מפורטת ומקצועית.

**חלופה 3 – ממוקדת קהילה / דיירים (בגובה העיניים):**
פוסט חם, אישי ואמפתי שפונה ישירות לדיירים או לקהילה.

לכל חלופה הוסף בסוף שורת האשטאגים רלוונטיים (3-5 האשטאגים).

פרמט את התשובה בצורה ברורה עם כותרת לכל חלופה."""

# ---------- Generate ----------
if generate:
    if not api_key:
        st.error("⚠️ יש להזין מפתח API של Anthropic בסיידבר.")
    elif not topic.strip():
        st.error("⚠️ יש להזין נושא או טקסט לפוסט.")
    else:
        with st.spinner("✍️ מנסח את הפוסטים..."):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": USER_PROMPT_TEMPLATE.format(topic=topic.strip()),
                        }
                    ],
                )
                response_text = message.content[0].text

                st.success("✅ הפוסטים מוכנים!")
                st.divider()

                # Display in a styled container
                st.markdown(
                    f'<div class="post-card">{response_text}</div>',
                    unsafe_allow_html=True,
                )

                # Copy-friendly version in expander
                with st.expander("📋 גרסה להעתקה (טקסט נקי)"):
                    st.code(response_text, language=None)

            except anthropic.AuthenticationError:
                st.error("❌ מפתח ה-API אינו תקין. בדוק ונסה שוב.")
            except anthropic.APIError as e:
                st.error(f"❌ שגיאת API: {e}")
