document.addEventListener("DOMContentLoaded", () => {

    const chatForm = document.getElementById("tankAiForm");
    const questionInput = document.getElementById("tankAiQuestion");
    const messages = document.getElementById("tankAiMessages");

    const quickPromptButtons =
        document.querySelectorAll("[data-tank-ai-prompt]");

    const revisionForm =
        document.querySelector('.tank-revision-form[data-loading-form]');

    const deleteOpen = document.getElementById("tankDeleteOpen");
    const deleteModal = document.getElementById("tankDeleteModal");

    const deleteCloseButtons =
        document.querySelectorAll("[data-delete-close]");


    function scrollChatToBottom() {
        if (!messages) return;
        messages.scrollTop = messages.scrollHeight;
    }


    scrollChatToBottom();


    quickPromptButtons.forEach(button => {
        button.addEventListener("click", () => {
            if (!questionInput) return;

            questionInput.value =
                button.dataset.tankAiPrompt || "";

            questionInput.focus();

            questionInput.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });
        });
    });


    function removeEmptyState() {
        messages
            ?.querySelector(".tank-ai-empty")
            ?.remove();
    }


    function createUserMessage(text) {
        const message = document.createElement("div");

        message.className =
            "tank-ai-message tank-ai-message-user";

        const label = document.createElement("div");
        label.className = "tank-ai-message-label";

        const badge = document.createElement("span");
        badge.textContent =
            messages?.dataset.userInitial || "S";

        label.appendChild(badge);
        label.append(document.createTextNode(" SEN"));

        const paragraph = document.createElement("p");
        paragraph.textContent = text;

        message.appendChild(label);
        message.appendChild(paragraph);

        messages.appendChild(message);
    }


    function createAssistantMessage() {
        const message = document.createElement("div");

        message.className =
            "tank-ai-message " +
            "tank-ai-message-assistant " +
            "is-streaming";

        const label = document.createElement("div");
        label.className = "tank-ai-message-label";

        const badge = document.createElement("span");
        badge.textContent = "✦";

        label.appendChild(badge);
        label.append(
            document.createTextNode(" SEMİH.AKVARYUM AI")
        );

        const paragraph = document.createElement("p");

        const thinking = document.createElement("span");
        thinking.className = "tank-ai-thinking";
        thinking.textContent = "Yanıt hazırlanıyor";

        paragraph.appendChild(thinking);

        message.appendChild(label);
        message.appendChild(paragraph);
        messages.appendChild(message);

        return {
            message,
            paragraph,
        };
    }


    function setChatLoading(loading) {
        if (!chatForm || !questionInput) return;

        const button =
            chatForm.querySelector('button[type="submit"]');

        const label = button?.querySelector("b");

        chatForm.classList.toggle(
            "is-streaming",
            loading
        );

        questionInput.disabled = loading;

        if (button) {
            button.disabled = loading;
        }

        if (label) {
            label.textContent =
                loading
                    ? "Yanıt geliyor..."
                    : "AI'ya Sor";
        }
    }


    function parseSseBlock(block) {
        let eventName = "message";
        const dataLines = [];

        block.split("\n").forEach(line => {
            if (line.startsWith("event:")) {
                eventName = line.slice(6).trim();
            }

            if (line.startsWith("data:")) {
                dataLines.push(
                    line.slice(5).trimStart()
                );
            }
        });

        return {
            eventName,
            data: dataLines.join("\n"),
        };
    }


    async function streamQuestion(question) {
        const streamUrl = chatForm.dataset.streamUrl;

        if (!streamUrl) {
            throw new Error(
                "Streaming adresi bulunamadı."
            );
        }

        removeEmptyState();
        createUserMessage(question);

        const assistant =
            createAssistantMessage();

        scrollChatToBottom();
        setChatLoading(true);

        let answerStarted = false;
        let completeAnswer = "";

        try {
            const response = await fetch(
                streamUrl,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },

                    credentials: "same-origin",

                    body: JSON.stringify({
                        question,
                    }),
                }
            );

            if (!response.ok) {
                let message =
                    "AI isteği gönderilemedi.";

                try {
                    const errorData =
                        await response.json();

                    if (errorData?.error) {
                        message = errorData.error;
                    }
                } catch (_) {}

                throw new Error(message);
            }

            if (!response.body) {
                throw new Error(
                    "Tarayıcı streaming yanıtını okuyamadı."
                );
            }

            const reader =
                response.body.getReader();

            const decoder =
                new TextDecoder("utf-8");

            let buffer = "";

            while (true) {
                const { value, done } =
                    await reader.read();

                if (done) break;

                buffer += decoder.decode(
                    value,
                    { stream: true }
                );

                const blocks =
                    buffer.split("\n\n");

                buffer =
                    blocks.pop() || "";

                for (const block of blocks) {
                    if (!block.trim()) continue;

                    const parsed =
                        parseSseBlock(block);

                    let payload = {};

                    if (parsed.data) {
                        try {
                            payload =
                                JSON.parse(
                                    parsed.data
                                );
                        } catch (_) {}
                    }

                    if (parsed.eventName === "delta") {
                        const text =
                            payload.text || "";

                        if (!text) continue;

                        if (!answerStarted) {
                            assistant.paragraph.textContent = "";
                            answerStarted = true;
                        }

                        completeAnswer += text;
                        assistant.paragraph.textContent =
                            completeAnswer;

                        scrollChatToBottom();
                    }

                    if (parsed.eventName === "error") {
                        throw new Error(
                            payload.message
                            || "AI yanıtı alınamadı."
                        );
                    }

                    if (parsed.eventName === "done") {
                        assistant.message.classList.remove(
                            "is-streaming"
                        );
                    }
                }
            }

            if (!completeAnswer.trim()) {
                throw new Error(
                    "AI boş yanıt döndürdü."
                );
            }

            assistant.message.classList.remove(
                "is-streaming"
            );

            questionInput.value = "";

        } catch (error) {
            assistant.message.classList.remove(
                "is-streaming"
            );

            assistant.paragraph.classList.add(
                "tank-ai-stream-error"
            );

            assistant.paragraph.textContent =
                error.message
                || "AI yanıtı alınamadı.";

        } finally {
            setChatLoading(false);
            questionInput.focus();
            scrollChatToBottom();
        }
    }


    if (chatForm) {
        chatForm.addEventListener(
            "submit",
            event => {
                event.preventDefault();

                if (
                    !questionInput
                    || questionInput.disabled
                ) {
                    return;
                }

                const question =
                    questionInput.value.trim();

                if (question.length < 2) {
                    questionInput.focus();
                    return;
                }

                streamQuestion(question);
            }
        );
    }


    if (revisionForm) {
        revisionForm.addEventListener(
            "submit",
            () => {
                const submitButton =
                    revisionForm.querySelector(
                        'button[type="submit"]'
                    );

                if (!submitButton) return;

                const label =
                    submitButton.querySelector("b");

                const loadingText =
                    submitButton.dataset.loadingText;

                if (label && loadingText) {
                    label.textContent = loadingText;
                }

                submitButton.disabled = true;

                revisionForm.classList.add(
                    "is-loading"
                );
            }
        );
    }


    function openDeleteModal() {
        if (!deleteModal) return;

        deleteModal.classList.add("is-open");
        deleteModal.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.style.overflow =
            "hidden";
    }


    function closeDeleteModal() {
        if (!deleteModal) return;

        deleteModal.classList.remove("is-open");
        deleteModal.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.style.overflow =
            "";
    }


    deleteOpen?.addEventListener(
        "click",
        openDeleteModal
    );


    deleteCloseButtons.forEach(button => {
        button.addEventListener(
            "click",
            closeDeleteModal
        );
    });


    document.addEventListener(
        "keydown",
        event => {
            if (event.key === "Escape") {
                closeDeleteModal();
            }
        }
    );

});
