/*
============================================================
EduCertify — Quiz Taking Engine
============================================================
Features:
- Starts quiz through REST API
- Loads questions safely
- Displays Option A/B/C/D text
- Supports Previous / Next
- Saves selected answers in current quiz session
- Progress dots
- Countdown timer
- Submits answers to server
- Redirects to result page
============================================================
*/

document.addEventListener("DOMContentLoaded", function () {

    const startBtn = document.getElementById("startQuizBtn");

    /*
    The quiz.js file is also loaded on pages where a quiz
    may not exist. Simply stop if there is no start button.
    */
    if (!startBtn) {
        return;
    }

    const quizId = startBtn.dataset.quizId;

    const startScreen = document.getElementById("quizStartScreen");
    const questionScreen = document.getElementById("quizQuestionScreen");

    const progressText = document.getElementById("quizProgressText");
    const dotsContainer = document.getElementById("quizDots");
    const questionText = document.getElementById("quizQuestionText");
    const optionsContainer = document.getElementById("quizOptions");

    const prevBtn = document.getElementById("prevQuestionBtn");
    const nextBtn = document.getElementById("nextQuestionBtn");
    const submitBtn = document.getElementById("submitQuizBtn");

    const timerElement = document.getElementById("quizTimer");

    /*
    ============================================================
    QUIZ STATE
    ============================================================
    */

    const state = {
        attemptId: null,
        questions: [],
        currentIndex: 0,
        answers: {},
        timeLimitSeconds: null,
        remainingSeconds: null,
        timerInterval: null,
        submitting: false
    };


    /*
    ============================================================
    SAFE VALUE HELPERS
    ============================================================
    */

    function safeText(value) {
        if (value === null || value === undefined) {
            return "";
        }

        return String(value);
    }


    /*
    Normalize question data.

    This handles:
        OptionA
        OptionB
        OptionC
        OptionD

    and also protects against APIs returning:
        option_a
        option_b
        option_c
        option_d

    It also handles an accidental nested "question" object.
    */

    function normalizeQuestion(rawQuestion) {

        if (!rawQuestion) {
            return null;
        }

        const q = rawQuestion.question || rawQuestion;

        return {
            QuestionID:
                q.QuestionID ??
                q.question_id ??
                q.id,

            QuestionText:
                safeText(
                    q.QuestionText ??
                    q.question_text ??
                    q.text ??
                    q.question
                ),

            OptionA:
                safeText(
                    q.OptionA ??
                    q.option_a ??
                    q.A ??
                    q.a
                ),

            OptionB:
                safeText(
                    q.OptionB ??
                    q.option_b ??
                    q.B ??
                    q.b
                ),

            OptionC:
                safeText(
                    q.OptionC ??
                    q.option_c ??
                    q.C ??
                    q.c
                ),

            OptionD:
                safeText(
                    q.OptionD ??
                    q.option_d ??
                    q.D ??
                    q.d
                ),

            Marks:
                Number(
                    q.Marks ??
                    q.marks ??
                    1
                )
        };
    }


    /*
    ============================================================
    EXTRACT QUESTIONS FROM API RESPONSE
    ============================================================
    */

    function extractQuestions(result) {

        let questions = result?.questions;

        /*
        Support APIs that return:
            {
                questions: [...]
            }

        or:
            {
                data: {
                    questions: [...]
                }
            }
        */

        if (!Array.isArray(questions)) {

            if (
                result?.data &&
                Array.isArray(result.data.questions)
            ) {
                questions = result.data.questions;
            }
        }

        /*
        Some APIs may return:
            data: [...]
        */

        if (!Array.isArray(questions)) {

            if (Array.isArray(result?.data)) {
                questions = result.data;
            }
        }

        if (!Array.isArray(questions)) {
            return [];
        }

        return questions
            .map(normalizeQuestion)
            .filter(function (question) {

                return (
                    question &&
                    question.QuestionID !== undefined &&
                    question.QuestionID !== null
                );
            });
    }


    /*
    ============================================================
    START QUIZ
    ============================================================
    */

    startBtn.addEventListener("click", async function () {

        if (startBtn.disabled) {
            return;
        }

        startBtn.disabled = true;
        startBtn.textContent = "Starting...";

        try {

            const result = await ecFetch(
                `/api/quizzes/${quizId}/start`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                }
            );

            if (!result || !result.success) {

                throw new Error(
                    result?.message ||
                    "Could not start quiz."
                );
            }

            /*
            ----------------------------------------------------
            Attempt ID
            ----------------------------------------------------
            */

            state.attemptId =
                result.attempt_id ??
                result.attemptId ??
                result.data?.attempt_id ??
                result.data?.attemptId;

            /*
            ----------------------------------------------------
            Questions
            ----------------------------------------------------
            */

            state.questions = extractQuestions(result);

            /*
            ----------------------------------------------------
            Time limit
            ----------------------------------------------------
            */

            const timeLimit =
                result.time_limit ??
                result.timeLimit ??
                result.data?.time_limit ??
                result.data?.timeLimit;

            if (
                timeLimit !== null &&
                timeLimit !== undefined &&
                Number(timeLimit) > 0
            ) {

                state.timeLimitSeconds =
                    Number(timeLimit) * 60;

                state.remainingSeconds =
                    state.timeLimitSeconds;

            } else {

                state.timeLimitSeconds = null;
                state.remainingSeconds = null;
            }


            /*
            ----------------------------------------------------
            Validate API response
            ----------------------------------------------------
            */

            if (!state.attemptId) {

                throw new Error(
                    "Quiz attempt ID was not returned by the server."
                );
            }

            if (state.questions.length === 0) {

                throw new Error(
                    "No quiz questions were returned by the server."
                );
            }


            /*
            ----------------------------------------------------
            Show quiz
            ----------------------------------------------------
            */

            if (startScreen) {
                startScreen.style.display = "none";
            }

            if (questionScreen) {
                questionScreen.style.display = "block";
            }

            state.currentIndex = 0;
            state.answers = {};

            renderQuestion();

            if (state.timeLimitSeconds) {
                startTimer();
            }

        } catch (error) {

            console.error(
                "EduCertify quiz start error:",
                error
            );

            alert(
                error.message ||
                "Could not start quiz."
            );

            startBtn.disabled = false;
            startBtn.textContent = "Start Quiz";
        }
    });


    /*
    ============================================================
    RENDER QUESTION
    ============================================================
    */

    function renderQuestion() {

        if (!state.questions.length) {
            return;
        }

        const q =
            state.questions[state.currentIndex];

        const total =
            state.questions.length;

        const questionNumber =
            state.currentIndex + 1;


        /*
        --------------------------------------------------------
        Question counter
        --------------------------------------------------------
        */

        if (progressText) {

            progressText.textContent =
                `Question ${questionNumber} of ${total}`;
        }


        /*
        --------------------------------------------------------
        Progress dots
        --------------------------------------------------------
        */

        if (dotsContainer) {

            dotsContainer.innerHTML = "";

            state.questions.forEach(
                function (question, index) {

                    const dot =
                        document.createElement("div");

                    let classes =
                        "ec-quiz-dot";

                    if (
                        state.answers[
                            question.QuestionID
                        ]
                    ) {
                        classes += " answered";
                    }

                    if (
                        index === state.currentIndex
                    ) {
                        classes += " current";
                    }

                    dot.className = classes;

                    dotsContainer.appendChild(dot);
                }
            );
        }


        /*
        --------------------------------------------------------
        Question text
        --------------------------------------------------------
        */

        if (questionText) {

            questionText.textContent =
                q.QuestionText ||
                "Question text unavailable.";
        }


        /*
        --------------------------------------------------------
        Options
        --------------------------------------------------------
        */

        if (optionsContainer) {

            optionsContainer.innerHTML = "";

            const options = [
                {
                    letter: "A",
                    text: q.OptionA
                },
                {
                    letter: "B",
                    text: q.OptionB
                },
                {
                    letter: "C",
                    text: q.OptionC
                },
                {
                    letter: "D",
                    text: q.OptionD
                }
            ];


            options.forEach(
                function (option) {

                    const label =
                        document.createElement("label");

                    label.className =
                        "ec-quiz-option";

                    label.dataset.letter =
                        option.letter;


                    /*
                    ------------------------------------------------
                    Selected state
                    ------------------------------------------------
                    */

                    const selected =
                        state.answers[
                            q.QuestionID
                        ] === option.letter;

                    if (selected) {
                        label.classList.add("selected");
                    }


                    /*
                    ------------------------------------------------
                    Radio input
                    ------------------------------------------------
                    */

                    const input =
                        document.createElement("input");

                    input.type = "radio";

                    input.name =
                        `q_${q.QuestionID}`;

                    input.value =
                        option.letter;

                    input.checked =
                        selected;


                    /*
                    ------------------------------------------------
                    Letter
                    ------------------------------------------------
                    */

                    const letterSpan =
                        document.createElement("span");

                    letterSpan.className =
                        "ec-option-letter";

                    letterSpan.textContent =
                        option.letter;


                    /*
                    ------------------------------------------------
                    Text
                    ------------------------------------------------
                    */

                    const textSpan =
                        document.createElement("span");

                    textSpan.className =
                        "ec-option-text";

                    textSpan.textContent =
                        option.text ||
                        "Option not available";


                    /*
                    ------------------------------------------------
                    Build option
                    ------------------------------------------------
                    */

                    label.appendChild(input);
                    label.appendChild(letterSpan);
                    label.appendChild(textSpan);

                    optionsContainer.appendChild(label);


                    /*
                    ------------------------------------------------
                    Selection
                    ------------------------------------------------
                    */

                    label.addEventListener(
                        "click",
                        function () {

                            state.answers[
                                q.QuestionID
                            ] = option.letter;

                            renderQuestion();
                        }
                    );
                }
            );
        }


        /*
        --------------------------------------------------------
        Navigation
        --------------------------------------------------------
        */

        const isFirst =
            state.currentIndex === 0;

        const isLast =
            state.currentIndex === total - 1;


        if (prevBtn) {
            prevBtn.disabled = isFirst;
        }


        if (nextBtn) {

            nextBtn.style.display =
                isLast
                    ? "none"
                    : "inline-flex";
        }


        if (submitBtn) {

            submitBtn.style.display =
                isLast
                    ? "inline-flex"
                    : "none";
        }
    }


    /*
    ============================================================
    PREVIOUS QUESTION
    ============================================================
    */

    if (prevBtn) {

        prevBtn.addEventListener(
            "click",
            function () {

                if (
                    state.currentIndex > 0
                ) {

                    state.currentIndex--;

                    renderQuestion();
                }
            }
        );
    }


    /*
    ============================================================
    NEXT QUESTION
    ============================================================
    */

    if (nextBtn) {

        nextBtn.addEventListener(
            "click",
            function () {

                if (
                    state.currentIndex <
                    state.questions.length - 1
                ) {

                    state.currentIndex++;

                    renderQuestion();
                }
            }
        );
    }


    /*
    ============================================================
    SUBMIT BUTTON
    ============================================================
    */

    if (submitBtn) {

        submitBtn.addEventListener(
            "click",
            async function () {

                await submitQuiz();
            }
        );
    }


    /*
    ============================================================
    TIMER
    ============================================================
    */

    function startTimer() {

        if (!timerElement) {
            return;
        }

        if (!state.remainingSeconds) {
            return;
        }

        updateTimerDisplay();


        state.timerInterval =
            setInterval(
                function () {

                    state.remainingSeconds--;

                    updateTimerDisplay();


                    if (
                        state.remainingSeconds <= 60
                    ) {

                        timerElement.classList.add(
                            "ec-timer-low"
                        );
                    }


                    if (
                        state.remainingSeconds <= 0
                    ) {

                        clearInterval(
                            state.timerInterval
                        );

                        state.timerInterval = null;

                        submitQuiz(true);
                    }

                },
                1000
            );
    }


    /*
    ============================================================
    UPDATE TIMER
    ============================================================
    */

    function updateTimerDisplay() {

        if (!timerElement) {
            return;
        }

        const remaining =
            Math.max(
                0,
                state.remainingSeconds || 0
            );

        const minutes =
            Math.floor(
                remaining / 60
            );

        const seconds =
            remaining % 60;

        timerElement.innerHTML =
            `<i class="fa-regular fa-clock"></i> ` +
            `${minutes}:${String(seconds).padStart(2, "0")}`;
    }


    /*
    ============================================================
    SUBMIT QUIZ
    ============================================================
    */

    async function submitQuiz(autoSubmit = false) {

        if (state.submitting) {
            return;
        }

        state.submitting = true;


        if (state.timerInterval) {

            clearInterval(
                state.timerInterval
            );

            state.timerInterval = null;
        }


        if (submitBtn) {

            submitBtn.disabled = true;

            submitBtn.textContent =
                autoSubmit
                    ? "Time Up — Submitting..."
                    : "Submitting...";
        }


        /*
        --------------------------------------------------------
        Check unanswered questions
        --------------------------------------------------------
        */

        if (!autoSubmit) {

            const unanswered =
                state.questions.filter(
                    function (question) {

                        return !state.answers[
                            question.QuestionID
                        ];
                    }
                );

            if (unanswered.length > 0) {

                const confirmSubmit =
                    window.confirm(
                        `You have ${unanswered.length} ` +
                        `unanswered question(s).\n\n` +
                        `Do you want to submit anyway?`
                    );

                if (!confirmSubmit) {

                    state.submitting = false;

                    if (submitBtn) {

                        submitBtn.disabled = false;

                        submitBtn.textContent =
                            "Submit Quiz";
                    }

                    if (
                        state.timeLimitSeconds &&
                        state.remainingSeconds > 0
                    ) {
                        startTimer();
                    }

                    return;
                }
            }
        }


        /*
        --------------------------------------------------------
        Prepare answers
        --------------------------------------------------------
        */

        const cleanAnswers = {};

        Object.keys(state.answers)
            .forEach(
                function (questionId) {

                    const answer =
                        state.answers[questionId];

                    if (
                        ["A", "B", "C", "D"]
                            .includes(answer)
                    ) {

                        cleanAnswers[
                            String(questionId)
                        ] = answer;
                    }
                }
            );


        try {

            const result =
                await ecFetch(
                    `/api/quizzes/${quizId}/submit`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify({
                            attempt_id:
                                state.attemptId,

                            answers:
                                cleanAnswers
                        })
                    }
                );


            if (!result || !result.success) {

                throw new Error(
                    result?.message ||
                    "Could not submit quiz."
                );
            }


            /*
            ----------------------------------------------------
            Result page
            ----------------------------------------------------
            */

            window.location.href =
                `/quiz/attempt/` +
                `${state.attemptId}/result`;


        } catch (error) {

            console.error(
                "EduCertify quiz submit error:",
                error
            );

            alert(
                error.message ||
                "Could not submit quiz."
            );

            state.submitting = false;

            if (submitBtn) {

                submitBtn.disabled = false;

                submitBtn.textContent =
                    "Submit Quiz";
            }


            if (
                state.timeLimitSeconds &&
                state.remainingSeconds > 0
            ) {

                startTimer();
            }
        }
    }

});