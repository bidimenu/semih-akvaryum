document.addEventListener(
    "DOMContentLoaded",
    () => {

        const form =
            document.getElementById(
                "analysisChatForm"
            );

        if (!form) {
            return;
        }

        const input =
            document.getElementById(
                "analysisChatQuestion"
            );

        const messages =
            document.getElementById(
                "analysisChatMessages"
            );

        const analysisDataNode =
            document.getElementById(
                "analysisContextData"
            );

        const formDataNode =
            document.getElementById(
                "analysisFormData"
            );

        const quickPrompts =
            document.querySelectorAll(
                "[data-analysis-prompt]"
            );

        let analysisContext = {};
        let formContext = {};

        const chatHistory = [];


        try {
            analysisContext =
                JSON.parse(
                    analysisDataNode
                        ?.textContent
                    || "{}"
                );
        } catch (_) {}

        try {
            formContext =
                JSON.parse(
                    formDataNode
                        ?.textContent
                    || "{}"
                );
        } catch (_) {}


        function scrollToBottom() {

            if (!messages) {
                return;
            }

            messages.scrollTop =
                messages.scrollHeight;

        }


        function removeEmptyState() {

            messages
                ?.querySelector(
                    ".analysis-chat-empty"
                )
                ?.remove();

        }


        function createLabel(
            type
        ) {

            const label =
                document.createElement(
                    "div"
                );

            label.className =
                "analysis-chat-label";

            const badge =
                document.createElement(
                    "span"
                );

            if (
                type === "assistant"
            ) {
                badge.textContent = "✦";

                label.appendChild(
                    badge
                );

                label.append(
                    document
                        .createTextNode(
                            " SEMİH.AKVARYUM AI"
                        )
                );

            } else {
                badge.textContent = "S";

                label.appendChild(
                    badge
                );

                label.append(
                    document
                        .createTextNode(
                            " SEN"
                        )
                );
            }

            return label;
        }


        function createUserMessage(
            text
        ) {

            const message =
                document.createElement(
                    "div"
                );

            message.className =
                "analysis-chat-message " +
                "analysis-chat-message-user";

            const paragraph =
                document.createElement(
                    "p"
                );

            paragraph.textContent =
                text;

            message.appendChild(
                createLabel("user")
            );

            message.appendChild(
                paragraph
            );

            messages.appendChild(
                message
            );

        }


        function createAssistantMessage() {

            const message =
                document.createElement(
                    "div"
                );

            message.className =
                "analysis-chat-message " +
                "analysis-chat-message-assistant " +
                "is-streaming";

            const paragraph =
                document.createElement(
                    "p"
                );

            const thinking =
                document.createElement(
                    "span"
                );

            thinking.className =
                "analysis-chat-thinking";

            thinking.textContent =
                "Analizi okuyorum";

            paragraph.appendChild(
                thinking
            );

            message.appendChild(
                createLabel(
                    "assistant"
                )
            );

            message.appendChild(
                paragraph
            );

            messages.appendChild(
                message
            );

            return {
                message,
                paragraph,
            };
        }


        function setLoading(
            loading
        ) {

            const button =
                form.querySelector(
                    'button[type="submit"]'
                );

            const label =
                button?.querySelector(
                    "b"
                );

            form.classList.toggle(
                "is-streaming",
                loading
            );

            input.disabled = loading;

            if (button) {
                button.disabled =
                    loading;
            }

            if (label) {
                label.textContent =
                    loading
                    ? "Yanıt geliyor..."
                    : "AI'ya Sor";
            }

        }


        function parseSseBlock(
            block
        ) {

            let eventName =
                "message";

            const dataLines = [];

            block
                .split("\n")
                .forEach(
                    line => {

                        if (
                            line.startsWith(
                                "event:"
                            )
                        ) {
                            eventName =
                                line
                                    .slice(6)
                                    .trim();
                        }

                        if (
                            line.startsWith(
                                "data:"
                            )
                        ) {
                            dataLines.push(
                                line
                                    .slice(5)
                                    .trimStart()
                            );
                        }

                    }
                );

            return {
                eventName,
                data:
                    dataLines.join(
                        "\n"
                    ),
            };
        }


        async function sendQuestion(
            question
        ) {

            removeEmptyState();

            createUserMessage(
                question
            );

            const assistant =
                createAssistantMessage();

            scrollToBottom();

            setLoading(true);

            let answerStarted =
                false;

            let completeAnswer =
                "";

            try {

                const response =
                    await fetch(
                        form.dataset
                            .streamUrl,
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                "Accept":
                                    "text/event-stream",
                            },

                            credentials:
                                "same-origin",

                            body:
                                JSON.stringify(
                                    {
                                        question,

                                        analysis:
                                            analysisContext,

                                        form_data:
                                            formContext,

                                        history:
                                            chatHistory
                                                .slice(-6),
                                    }
                                ),
                        }
                    );


                if (!response.ok) {

                    let message =
                        "AI isteği gönderilemedi.";

                    try {
                        const data =
                            await response
                                .json();

                        if (
                            data?.error
                        ) {
                            message =
                                data.error;
                        }
                    } catch (_) {}

                    throw new Error(
                        message
                    );
                }


                if (!response.body) {
                    throw new Error(
                        "Tarayıcı streaming yanıtını okuyamadı."
                    );
                }


                const reader =
                    response.body
                        .getReader();

                const decoder =
                    new TextDecoder(
                        "utf-8"
                    );

                let buffer = "";


                while (true) {

                    const {
                        value,
                        done,
                    } =
                        await reader
                            .read();

                    if (done) {
                        break;
                    }

                    buffer +=
                        decoder.decode(
                            value,
                            {
                                stream:
                                    true,
                            }
                        );

                    const blocks =
                        buffer.split(
                            "\n\n"
                        );

                    buffer =
                        blocks.pop()
                        || "";

                    for (
                        const block
                        of blocks
                    ) {

                        if (
                            !block.trim()
                        ) {
                            continue;
                        }

                        const parsed =
                            parseSseBlock(
                                block
                            );

                        let payload =
                            {};

                        if (
                            parsed.data
                        ) {

                            try {
                                payload =
                                    JSON.parse(
                                        parsed.data
                                    );
                            } catch (_) {}

                        }


                        if (
                            parsed.eventName
                            === "delta"
                        ) {

                            const text =
                                payload.text
                                || "";

                            if (!text) {
                                continue;
                            }

                            if (
                                !answerStarted
                            ) {
                                assistant
                                    .paragraph
                                    .textContent =
                                        "";

                                answerStarted =
                                    true;
                            }

                            completeAnswer +=
                                text;

                            assistant
                                .paragraph
                                .textContent =
                                    completeAnswer;

                            scrollToBottom();
                        }


                        if (
                            parsed.eventName
                            === "error"
                        ) {

                            throw new Error(
                                payload.message
                                || "AI yanıtı alınamadı."
                            );

                        }


                        if (
                            parsed.eventName
                            === "done"
                        ) {

                            assistant
                                .message
                                .classList
                                .remove(
                                    "is-streaming"
                                );

                        }

                    }

                }


                if (
                    !completeAnswer
                        .trim()
                ) {
                    throw new Error(
                        "AI boş yanıt döndürdü."
                    );
                }


                assistant
                    .message
                    .classList
                    .remove(
                        "is-streaming"
                    );


                chatHistory.push(
                    {
                        role:
                            "user",
                        content:
                            question,
                    },
                    {
                        role:
                            "assistant",
                        content:
                            completeAnswer,
                    }
                );


                if (
                    chatHistory.length
                    > 12
                ) {
                    chatHistory.splice(
                        0,
                        chatHistory.length
                        - 12
                    );
                }


                input.value = "";

            } catch (error) {

                assistant
                    .message
                    .classList
                    .remove(
                        "is-streaming"
                    );

                assistant
                    .paragraph
                    .classList
                    .add(
                        "analysis-chat-stream-error"
                    );

                assistant
                    .paragraph
                    .textContent =
                        error.message
                        || "AI yanıtı alınamadı.";

            } finally {

                setLoading(false);

                input.focus();

                scrollToBottom();

            }

        }


        form.addEventListener(
            "submit",
            event => {

                event.preventDefault();

                if (
                    input.disabled
                ) {
                    return;
                }

                const question =
                    input.value.trim();

                if (
                    question.length
                    < 2
                ) {
                    input.focus();
                    return;
                }

                sendQuestion(
                    question
                );

            }
        );


        quickPrompts
            .forEach(
                button => {

                    button
                        .addEventListener(
                            "click",
                            () => {

                                input.value =
                                    button
                                        .dataset
                                        .analysisPrompt
                                    || "";

                                input.focus();

                                form.scrollIntoView(
                                    {
                                        behavior:
                                            "smooth",

                                        block:
                                            "center",
                                    }
                                );

                            }
                        );

                }
            );


        scrollToBottom();

    }
);
