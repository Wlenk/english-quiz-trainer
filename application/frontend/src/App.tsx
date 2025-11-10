import  { useEffect, useState, useRef } from "react";
import { Button, Select, Spin, Typography, Input, message } from "antd";
import "antd/dist/reset.css";
import "./App.css";

const { Title, Text } = Typography;
const { Option } = Select;

type Activity = { uuid: string; name: string; words: string };
type Course = { name: string; words: string; activities: Activity[] };
type Dictionary = { name: string; tag: string; courses: Course[] };
type DictionariesResp = { config?: { title?: string }; dictionarys: Dictionary[] };
type Word = { index: number; answer: string[]; translate: string };
type Stage = "select_dict" | "select_course" | "select_activity" | "quiz";

export default function App() {
  const [stage, setStage] = useState<Stage>("select_dict");
  const [loading, setLoading] = useState(true);
  const [dictionaries, setDictionaries] = useState<Dictionary[]>([]);
  const [configTitle, setConfigTitle] = useState("Word Quiz");

  const [selectedDict, setSelectedDict] = useState<string | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedActivity, setSelectedActivity] = useState<string>("all");

  const [words, setWords] = useState<Word[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answerText, setAnswerText] = useState("");
  const [inputStartedAt, setInputStartedAt] = useState<number | null>(null);
  const [awaitingReport, setAwaitingReport] = useState(false);

  const [submitMessage, setSubmitMessage] = useState("");
  const [correctCount, setCorrectCount] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetchDictionaries();
  }, []);

  async function fetchDictionaries() {
    try {
      const res = await fetch("/api/dictionaries");
      if (!res.ok) throw new Error("Failed to fetch dictionaries");
      const data: DictionariesResp = await res.json();
      setDictionaries(data.dictionarys || []);
      if (data.config?.title) setConfigTitle(data.config.title);
    } catch (e) {
      message.error("Failed to load dictionaries");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleDictSelect(v: string) {
    setSelectedDict(v);
    const dict = dictionaries.find((d) => d.tag === v || d.name === v);
    if (dict) setCourses(dict.courses);
    setStage("select_course");
  }

  function handleCourseSelect(v: string) {
    setSelectedCourse(v);
    const dict = dictionaries.find((d) => d.tag === selectedDict);
    const course = dict?.courses.find((c) => c.name === v);
    if (course) setActivities(course.activities || []);
    setStage("select_activity");
  }

  async function startQuiz() {
    if (!selectedDict || !selectedCourse) return;
    setLoading(true);
    try {
      const payload = {
        dictionary: selectedDict,
        course: selectedCourse,
        activity: selectedActivity || "all",
      };
      const res = await fetch("/api/course", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setWords(data.words);
      setCurrentIdx(0);
      setCorrectCount(0);
      setWrongCount(0);
      setStage("quiz");
      playAudio(data.words[0]);
    } catch (e) {
      console.error(e);
      message.error("Failed to start quiz");
    } finally {
      setLoading(false);
    }
  }

  function playAudio(w: Word) {
    const url = `/api/voice?dictionary=${selectedDict}&course=${selectedCourse}&index=${w.index}`;
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.play().catch(() => {});
  }

  async function submitAnswer() {
    if (!sessionId || !words[currentIdx]) return;
    const w = words[currentIdx];
    const timecost = inputStartedAt ? (performance.now() - inputStartedAt) / 1000 : 0;
    setAwaitingReport(true);

    try {
      const payload = {
        course: `${selectedDict}/${selectedCourse}`,
        session_id: sessionId,
        index: w.index,
        answer: answerText,
        timecost,
      };
      const res = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.correct) {
        setSubmitMessage("✅ Correct");
        setCorrectCount((c) => c + 1);
      } else {
        const correctWord = w.answer[0];
        const correctTranslate = w.translate ? ` - ${w.translate}` : "";
        setSubmitMessage(`❌ Wrong\n${correctWord}${correctTranslate}`);
        setWrongCount((c) => c + 1);
      }


      setTimeout(() => {
        setSubmitMessage("");
        const next = currentIdx + 1;
        if (next < words.length) {
          setCurrentIdx(next);
          setAnswerText("");
          setInputStartedAt(null);
          playAudio(words[next]);
        } else {
          finalizeSession();
        }
        setAwaitingReport(false);
      }, 2000);
    } catch (e) {
      message.error("Submit error"+e);
      setAwaitingReport(false);
    }
  }

  async function finalizeSession() {
    if (!sessionId) return;
    const payload = { course: `${selectedDict}/${selectedCourse}`, session_id: sessionId, done: true };
    await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    message.success("🎉 Session complete!");
    setStage("select_dict");
  }

  const currentWord = words[currentIdx];

  return (
    <div className="container">
      {loading && <Spin size="large" />}
      {!loading && stage === "select_dict" && (
        <div className="page fade-in">
          <Title level={3}>{configTitle}</Title>
          <Select
            style={{ width: "80%" }}
            placeholder="Choose dictionary"
            onChange={handleDictSelect}
            size="large"
          >
            {dictionaries.map((d) => (
              <Option key={d.tag} value={d.tag}>{d.name}</Option>
            ))}
          </Select>
        </div>
      )}

      {!loading && stage === "select_course" && (
        <div className="page fade-in">
          <Title level={3}>{configTitle}</Title>
          <Select
            style={{ width: "80%" }}
            placeholder="Choose course"
            onChange={handleCourseSelect}
            size="large"
          >
            {courses.map((c) => (
              <Option key={c.name} value={c.name}>{c.name}</Option>
            ))}
          </Select>
        </div>
      )}

      {!loading && stage === "select_activity" && (
        <div className="page fade-in">
          <Title level={3}>{configTitle}</Title>
          <Select
            style={{ width: "80%" }}
            value={selectedActivity}
            onChange={setSelectedActivity}
            size="large"
          >
            <Option value="all">All</Option>
            {activities.map((a) => (
              <Option key={a.uuid} value={a.uuid}>{a.name}</Option>
            ))}
          </Select>
          <Button type="primary" style={{ marginTop: 20 }} onClick={startQuiz}>
            Start Quiz
          </Button>
        </div>
      )}

      {!loading && stage === "quiz" && currentWord && (
        <div className="page fade-in quiz-container">
          <Title level={4} style={{ textAlign: "center" }}>{configTitle}</Title>
          <Text type="secondary" style={{ textAlign: "center", marginBottom: 8 }}>
            {currentIdx + 1}/{words.length} | ✅ {correctCount} ❌ {wrongCount}
          </Text>

          <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", width: "100%" }}>
            <Input
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              onFocus={() => setInputStartedAt(performance.now())}
              placeholder="Type here..."
              style={{ width: "80%" }}
            />
          </div>

          <div className="message-display">{submitMessage && (
  <div style={{ marginBottom: 8, whiteSpace: "pre-line", textAlign: "center" }}>
    {submitMessage}
  </div>
)}
</div>
          <Button
            type="primary"
            className="submit-button"
            onClick={submitAnswer}
            disabled={awaitingReport}
          >
            Submit
          </Button>
        </div>
      )}
    </div>
  );
}
