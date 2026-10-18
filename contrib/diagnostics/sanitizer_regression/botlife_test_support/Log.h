#pragma once

// Evaluate arguments, without depending on the server logger or fmt.
template <typename... Args>
void TestLog(Args const&...) { }

#define TC_LOG_INFO(...) TestLog(__VA_ARGS__)
#define TC_LOG_WARN(...) TestLog(__VA_ARGS__)
