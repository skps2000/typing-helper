@echo off
chcp 65001 >nul
echo 실행 중인 타이핑 도우미/로거를 모두 종료합니다...
for %%N in (TypingHelper.exe TypingHelper_v4.exe TypingHelper_v5.exe TypingHelper_v6.exe TypingLogger.exe TypingLogger_console.exe TypingLogger_light.exe TypingLogger_v2.exe TypingLogger_debug.exe) do taskkill /F /IM %%N >nul 2>&1
echo 완료. 이제 TypingHelper_v6.exe 하나만 실행하세요.
pause
