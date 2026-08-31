// EduCertify — Quiz taking engine (fetch-based, no answers stored client-side pre-grading)

document.addEventListener("DOMContentLoaded", function () {
  const startBtn = document.getElementById("startQuizBtn");
  if (!startBtn) return;

  const quizId = startBtn.dataset.quizId;
  const quizContainer = document.getElementById("quizContainer");
  const startScreen = document.getElementById("quizStartScreen");
  const questionScreen = document.getElementById("quizQuestionScreen");

  let state = {
    attemptId: null,
    questions: [],
    currentIndex: 0,
    answers: {},
    timeLimitSeconds: null,
    timerInterval: null,
  };

  startBtn.addEventListener("click", async function () {
    startBtn.disabled = true;
    startBtn.textContent = "Starting...";

    const result = await ecFetch(`/api/quizzes/${quizId}/start`, { method: "POST" });

    if (!result.success) {
      alert(result.message || "Could not start quiz.");
      startBtn.disabled = false;
      startBtn.textContent = "Start Quiz";
      return;
    }

    state.attemptId = result.attempt_id;
    state.questions = result.questions;
    state.timeLimitSeconds = result.time_limit ? result.time_limit * 60 : null;

    startScreen.style.display = "none";
    questionScreen.style.display = "block";

    renderQuestion();
    if (state.timeLimitSeconds) startTimer();
  });

  function renderQuestion() {
    const q = state.questions[state.currentIndex];
    const total = state.questions.length;

    document.getElementById("quizProgressText").textContent = `Question ${state.currentIndex + 1} of ${total}`;

    const dotsHtml = state.questions
      .map((question, i) => {
        let cls = "ec-quiz-dot";
        if (state.answers[question.QuestionID]) cls += " answered";
        if (i === state.currentIndex) cls += " current";
        return `<div class="${cls}"></div>`;
      })
      .join("");
    document.getElementById("quizDots").innerHTML = dotsHtml;

    let optionsHtml = "";
    ["A", "B", "C", "D"].forEach(function (letter) {
      const optionText = q["Option" + letter];
      const selected = state.answers[q.QuestionID] === letter;
      optionsHtml += `
        <label class="ec-quiz-option ${selected ? "selected" : ""}" data-letter="${letter}">
          <input type="radio" name="q_${q.QuestionID}" value="${letter}" ${selected ? "checked" : ""}>
          ${optionText}
        </label>`;
    });

    document.getElementById("quizQuestionText").textContent = q.QuestionText;
    document.getElementById("quizOptions").innerHTML = optionsHtml;

    document.querySelectorAll(".ec-quiz-option").forEach(function (opt) {
      opt.addEventListener("click", function () {
        state.answers[q.QuestionID] = opt.dataset.letter;
        renderQuestion();
      });
    });

    document.getElementById("prevQuestionBtn").disabled = state.currentIndex === 0;
    const isLast = state.currentIndex === total - 1;
    document.getElementById("nextQuestionBtn").style.display = isLast ? "none" : "inline-flex";
    document.getElementById("submitQuizBtn").style.display = isLast ? "inline-flex" : "none";
  }

  document.getElementById("prevQuestionBtn")?.addEventListener("click", function () {
    if (state.currentIndex > 0) {
      state.currentIndex--;
      renderQuestion();
    }
  });

  document.getElementById("nextQuestionBtn")?.addEventListener("click", function () {
    if (state.currentIndex < state.questions.length - 1) {
      state.currentIndex++;
      renderQuestion();
    }
  });

  document.getElementById("submitQuizBtn")?.addEventListener("click", async function () {
    await submitQuiz();
  });

  function startTimer() {
    const timerEl = document.getElementById("quizTimer");
    let remaining = state.timeLimitSeconds;

    state.timerInterval = setInterval(function () {
      remaining -= 1;
      const minutes = Math.floor(remaining / 60);
      const seconds = remaining % 60;
      timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, "0")}`;

      if (remaining <= 60) timerEl.classList.add("ec-timer-low");

      if (remaining <= 0) {
        clearInterval(state.timerInterval);
        submitQuiz();
      }
    }, 1000);
  }

  async function submitQuiz() {
    if (state.timerInterval) clearInterval(state.timerInterval);

    const submitBtn = document.getElementById("submitQuizBtn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";
    }

    const result = await ecFetch(`/api/quizzes/${quizId}/submit`, {
      method: "POST",
      body: JSON.stringify({ attempt_id: state.attemptId, answers: state.answers }),
    });

    if (result.success) {
      window.location.href = `/quiz/attempt/${state.attemptId}/result`;
    } else {
      alert(result.message || "Could not submit quiz.");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit Quiz";
      }
    }
  }
});
