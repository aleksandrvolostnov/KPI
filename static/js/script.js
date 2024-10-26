document.addEventListener("DOMContentLoaded", function() {
    // Валидация форм
    const forms = document.querySelectorAll('form');

    if (forms.length > 0) {
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                let isValid = true;
                let firstInvalidInput = null;

                const inputs = form.querySelectorAll('input, select, textarea');

                inputs.forEach(input => {
                    if (input.required && !input.value.trim()) {
                        isValid = false;
                        input.classList.add('error');
                        input.setAttribute('aria-invalid', 'true');

                        if (!firstInvalidInput) {
                            firstInvalidInput = input;
                        }
                    } else {
                        input.classList.remove('error');
                        input.setAttribute('aria-invalid', 'false');
                    }
                });

                if (!isValid) {
                    e.preventDefault();
                    alert('Пожалуйста, заполните все обязательные поля.');
                    if (firstInvalidInput) {
                        firstInvalidInput.focus();
                    }
                }
            });
        });
    }

    // Логика отправки сообщений
    const messageInput = document.getElementById('message-input');
    const sendMessageButton = document.querySelector('.send-button');

    function sendMessage() {
        const message = messageInput.value.trim();

        if (!message) {
            alert('Введите сообщение!');
            messageInput.focus();
            return;
        }

        const formData = new FormData();
        formData.append('content', message);
        formData.append('receiver_id', receiverId);  // Нужно определить receiverId

        fetch('/chat/new_message', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                messageInput.value = ''; // Очищаем поле ввода
                showNotification(data.new_message.sender, data.new_message.content);
                updateUserIcons(data.new_message.sender);
            } else {
                console.error('Ошибка при отправке сообщения:', data.message);
                alert('Ошибка при отправке сообщения');
            }
        })
        .catch(error => {
            console.error('Ошибка сети при отправке сообщения:', error);
            alert('Ошибка сети при отправке сообщения');
        });
    }

    if (sendMessageButton) {
        sendMessageButton.addEventListener('click', sendMessage);
    }

    // Отправка сообщения по клавише Enter
    if (messageInput) {
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Показываем уведомление
    function showNotification(sender, content) {
        const notification = document.createElement('div');
        notification.classList.add('notification');
        notification.innerText = `Новое сообщение от ${sender}: ${content}`;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // Обновляем значки пользователей с точкой
    function updateUserIcons(sender) {
        const userElement = document.querySelector(`.user[data-username="${sender}"]`);
        if (userElement) {
            const dot = document.createElement('span');
            dot.classList.add('new-message-dot');
            userElement.appendChild(dot);
        }
    }

    // Стили для уведомлений и точки
    const style = document.createElement('style');
    style.innerHTML = `
        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: #ff6600;
            color: white;
            padding: 10px 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            font-family: 'Century Gothic';
            font-size: 16px;
        }

        .new-message-dot {
            width: 10px;
            height: 10px;
            background-color: red;
            border-radius: 50%;
            display: inline-block;
            margin-left: 5px;
        }
    `;
    document.head.appendChild(style);
});
