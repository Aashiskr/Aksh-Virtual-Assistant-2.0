// Aksh phone-approved Windows credential provider.
// Credential packing follows Microsoft's V2 Credential Provider sample.

#ifndef WIN32_NO_STATUS
#include <ntstatus.h>
#define WIN32_NO_STATUS
#endif
#include <windows.h>
#include <credentialprovider.h>
#include <intsafe.h>
#include <ntsecapi.h>
#define SECURITY_WIN32
#include <security.h>
#include <wincred.h>
#include <shlwapi.h>
#include <strsafe.h>
#include <unknwn.h>
#include <atomic>
#include <cstdint>
#include <new>
#include <string>
#include <vector>

#ifndef HRESULT_FROM_NT
#define HRESULT_FROM_NT(x) ((HRESULT)((x) | FACILITY_NT_BIT))
#endif

static const GUID CLSID_AkshCredentialProvider =
    {0xb7a1ed4b, 0x58c7, 0x4db9,
     {0x91, 0xc8, 0xa7, 0x33, 0xe4, 0x9e, 0x8d, 0x22}};
static const wchar_t* kReadyEvent = L"Global\\AkshPhoneUnlockReady";
static const wchar_t* kCredentialPipe =
    L"\\\\.\\pipe\\AkshPhoneUnlockCredential";
static constexpr uint32_t kPipeMagic = 0x48534B41;
static std::atomic<long> g_dllRefs{0};
static std::atomic<bool> g_ready{false};

enum FieldId { FI_LABEL, FI_TITLE, FI_STATUS, FI_SUBMIT, FI_COUNT };

struct FieldStatePair {
    CREDENTIAL_PROVIDER_FIELD_STATE state;
    CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE interactive;
};

static const CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR kFields[FI_COUNT] = {
    {FI_LABEL, CPFT_SMALL_TEXT, const_cast<PWSTR>(L"Aksh Phone Unlock"),
     GUID_NULL},
    {FI_TITLE, CPFT_LARGE_TEXT, const_cast<PWSTR>(L"Aksh Phone Unlock")},
    {FI_STATUS, CPFT_SMALL_TEXT,
     const_cast<PWSTR>(L"Approve with your phone fingerprint")},
    {FI_SUBMIT, CPFT_SUBMIT_BUTTON,
     const_cast<PWSTR>(L"Check phone approval")},
};

static const FieldStatePair kFieldStates[FI_COUNT] = {
    {CPFS_HIDDEN, CPFIS_NONE},
    {CPFS_DISPLAY_IN_BOTH, CPFIS_NONE},
    {CPFS_DISPLAY_IN_BOTH, CPFIS_NONE},
    {CPFS_DISPLAY_IN_SELECTED_TILE, CPFIS_NONE},
};

static HRESULT CopyFieldDescriptor(
    const CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR& source,
    CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR** destination) {
    *destination = static_cast<CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR*>(
        CoTaskMemAlloc(sizeof(CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR)));
    if (!*destination) return E_OUTOFMEMORY;
    **destination = source;
    (*destination)->pszLabel = nullptr;
    HRESULT hr = SHStrDupW(source.pszLabel, &(*destination)->pszLabel);
    if (FAILED(hr)) {
        CoTaskMemFree(*destination);
        *destination = nullptr;
    }
    return hr;
}

static HRESULT InitUnicodeString(PWSTR value, UNICODE_STRING* output) {
    USHORT bytes = 0;
    HRESULT hr = SizeTToUShort(wcslen(value) * sizeof(wchar_t), &bytes);
    if (FAILED(hr)) return hr;
    output->Length = bytes;
    output->MaximumLength = bytes;
    output->Buffer = value;
    return S_OK;
}

static HRESULT InitKerbLogon(
    PWSTR domain, PWSTR username, PWSTR password,
    CREDENTIAL_PROVIDER_USAGE_SCENARIO scenario,
    KERB_INTERACTIVE_UNLOCK_LOGON* output) {
    ZeroMemory(output, sizeof(*output));
    output->Logon.MessageType = scenario == CPUS_UNLOCK_WORKSTATION
        ? KerbWorkstationUnlockLogon : KerbInteractiveLogon;
    HRESULT hr = InitUnicodeString(domain, &output->Logon.LogonDomainName);
    if (SUCCEEDED(hr)) {
        hr = InitUnicodeString(username, &output->Logon.UserName);
    }
    if (SUCCEEDED(hr)) {
        hr = InitUnicodeString(password, &output->Logon.Password);
    }
    return hr;
}

static void PackUnicodeString(
    const UNICODE_STRING& source, BYTE*& cursor,
    BYTE* base, UNICODE_STRING* destination) {
    destination->Length = source.Length;
    destination->MaximumLength = source.Length;
    CopyMemory(cursor, source.Buffer, source.Length);
    destination->Buffer = reinterpret_cast<PWSTR>(cursor - base);
    cursor += source.Length;
}

static HRESULT PackKerbLogon(
    const KERB_INTERACTIVE_UNLOCK_LOGON& input,
    BYTE** bytes, DWORD* count) {
    DWORD total = sizeof(input) + input.Logon.LogonDomainName.Length
        + input.Logon.UserName.Length + input.Logon.Password.Length;
    auto output = static_cast<KERB_INTERACTIVE_UNLOCK_LOGON*>(
        CoTaskMemAlloc(total));
    if (!output) return E_OUTOFMEMORY;
    ZeroMemory(output, sizeof(*output));
    output->Logon.MessageType = input.Logon.MessageType;
    BYTE* base = reinterpret_cast<BYTE*>(output);
    BYTE* cursor = base + sizeof(*output);
    PackUnicodeString(
        input.Logon.LogonDomainName, cursor, base,
        &output->Logon.LogonDomainName);
    PackUnicodeString(
        input.Logon.UserName, cursor, base, &output->Logon.UserName);
    PackUnicodeString(
        input.Logon.Password, cursor, base, &output->Logon.Password);
    *bytes = base;
    *count = total;
    return S_OK;
}

static HRESULT RetrieveNegotiatePackage(ULONG* package) {
    HANDLE lsa = nullptr;
    NTSTATUS status = LsaConnectUntrusted(&lsa);
    if (status != 0) return HRESULT_FROM_NT(status);
    char name[] = NEGOSSP_NAME_A;
    LSA_STRING value{};
    value.Buffer = name;
    value.Length = static_cast<USHORT>(strlen(name));
    value.MaximumLength = value.Length + 1;
    status = LsaLookupAuthenticationPackage(lsa, &value, package);
    LsaDeregisterLogonProcess(lsa);
    return status == 0 ? S_OK : HRESULT_FROM_NT(status);
}

static HRESULT ProtectPassword(PCWSTR input, PWSTR* output) {
    *output = nullptr;
    PWSTR copy = nullptr;
    HRESULT hr = SHStrDupW(input, &copy);
    if (FAILED(hr)) return hr;
    DWORD chars = 0;
    BOOL initial = CredProtectW(
        FALSE, copy, static_cast<DWORD>(wcslen(copy) + 1),
        nullptr, &chars, nullptr);
    if (!initial && GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
        *output = static_cast<PWSTR>(
            CoTaskMemAlloc(chars * sizeof(wchar_t)));
        if (!*output) {
            hr = E_OUTOFMEMORY;
        } else if (!CredProtectW(
                       FALSE, copy,
                       static_cast<DWORD>(wcslen(copy) + 1),
                       *output, &chars, nullptr)) {
            hr = HRESULT_FROM_WIN32(GetLastError());
            CoTaskMemFree(*output);
            *output = nullptr;
        }
    } else {
        hr = E_UNEXPECTED;
    }
    SecureZeroMemory(copy, wcslen(copy) * sizeof(wchar_t));
    CoTaskMemFree(copy);
    return hr;
}

static bool ReadExact(HANDLE pipe, void* buffer, DWORD size) {
    BYTE* cursor = static_cast<BYTE*>(buffer);
    while (size) {
        DWORD read = 0;
        if (!ReadFile(pipe, cursor, size, &read, nullptr) || read == 0) {
            return false;
        }
        cursor += read;
        size -= read;
    }
    return true;
}

struct BrokerCredential {
    std::wstring domain;
    std::wstring username;
    std::wstring password;
    ~BrokerCredential() {
        if (!password.empty()) {
            SecureZeroMemory(
                password.data(), password.size() * sizeof(wchar_t));
        }
    }
};

static bool ReadWideField(
    HANDLE pipe, uint32_t bytes, std::wstring* value) {
    if (bytes == 0 || bytes > 8192 || bytes % sizeof(wchar_t) != 0) {
        return false;
    }
    std::vector<wchar_t> buffer(
        bytes / sizeof(wchar_t) + 1, L'\0');
    if (!ReadExact(pipe, buffer.data(), bytes)) return false;
    value->assign(buffer.data(), bytes / sizeof(wchar_t));
    return true;
}

static bool FetchCredential(BrokerCredential* credential) {
    if (!WaitNamedPipeW(kCredentialPipe, 5000)) return false;
    HANDLE pipe = CreateFileW(
        kCredentialPipe, GENERIC_READ, 0, nullptr,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return false;
    uint32_t header[4]{};
    bool ok = ReadExact(pipe, header, sizeof(header))
        && header[0] == kPipeMagic
        && ReadWideField(pipe, header[1], &credential->domain)
        && ReadWideField(pipe, header[2], &credential->username)
        && ReadWideField(pipe, header[3], &credential->password);
    CloseHandle(pipe);
    return ok;
}

class AkshCredential final : public ICredentialProviderCredential {
public:
    explicit AkshCredential(
        CREDENTIAL_PROVIDER_USAGE_SCENARIO scenario)
        : refs_(1), scenario_(scenario), events_(nullptr) {
        ++g_dllRefs;
    }

    IFACEMETHODIMP QueryInterface(
        REFIID riid, void** object) override {
        if (!object) return E_INVALIDARG;
        *object = nullptr;
        if (IsEqualIID(riid, IID_IUnknown)
            || IsEqualIID(
                riid, IID_ICredentialProviderCredential)) {
            *object =
                static_cast<ICredentialProviderCredential*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    IFACEMETHODIMP_(ULONG) AddRef() override {
        return ++refs_;
    }

    IFACEMETHODIMP_(ULONG) Release() override {
        long value = --refs_;
        if (!value) delete this;
        return value;
    }

    IFACEMETHODIMP Advise(
        ICredentialProviderCredentialEvents* events) override {
        if (events_) events_->Release();
        events_ = events;
        if (events_) events_->AddRef();
        return S_OK;
    }

    IFACEMETHODIMP UnAdvise() override {
        if (events_) events_->Release();
        events_ = nullptr;
        return S_OK;
    }

    IFACEMETHODIMP SetSelected(BOOL* autoLogon) override {
        *autoLogon = g_ready.load() ? TRUE : FALSE;
        return S_OK;
    }

    IFACEMETHODIMP SetDeselected() override {
        return S_OK;
    }

    IFACEMETHODIMP GetFieldState(
        DWORD id, CREDENTIAL_PROVIDER_FIELD_STATE* state,
        CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE* interactive)
        override {
        if (id >= FI_COUNT) return E_INVALIDARG;
        *state = kFieldStates[id].state;
        *interactive = kFieldStates[id].interactive;
        return S_OK;
    }

    IFACEMETHODIMP GetStringValue(
        DWORD id, PWSTR* value) override {
        if (!value || id >= FI_COUNT) return E_INVALIDARG;
        PCWSTR text = L"";
        if (id == FI_LABEL || id == FI_TITLE) {
            text = L"Aksh Phone Unlock";
        } else if (id == FI_STATUS) {
            text = g_ready.load()
                ? L"Phone approved. Unlocking Windows..."
                : L"Approve the Aksh notification with your phone fingerprint.";
        } else if (id == FI_SUBMIT) {
            text = L"Check phone approval";
        }
        return SHStrDupW(text, value);
    }

    IFACEMETHODIMP GetBitmapValue(
        DWORD, HBITMAP*) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetCheckboxValue(
        DWORD, BOOL*, PWSTR*) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetComboBoxValueCount(
        DWORD, DWORD*, DWORD*) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetComboBoxValueAt(
        DWORD, DWORD, PWSTR*) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetSubmitButtonValue(
        DWORD id, DWORD* adjacent) override {
        if (id != FI_SUBMIT) return E_INVALIDARG;
        *adjacent = FI_STATUS;
        return S_OK;
    }

    IFACEMETHODIMP SetStringValue(
        DWORD, PCWSTR) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP SetCheckboxValue(
        DWORD, BOOL) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP SetComboBoxSelectedValue(
        DWORD, DWORD) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP CommandLinkClicked(DWORD) override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetSerialization(
        CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE* response,
        CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* serialization,
        PWSTR* statusText,
        CREDENTIAL_PROVIDER_STATUS_ICON* statusIcon) override {
        *response = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
        *statusText = nullptr;
        *statusIcon = CPSI_NONE;
        ZeroMemory(serialization, sizeof(*serialization));
        BrokerCredential credential;
        if (!g_ready.load() || !FetchCredential(&credential)) {
            return SHStrDupW(
                L"Waiting for a fresh phone approval.", statusText);
        }
        g_ready.store(false);
        PWSTR protectedPassword = nullptr;
        HRESULT hr = ProtectPassword(
            credential.password.c_str(), &protectedPassword);
        if (SUCCEEDED(hr)) {
            KERB_INTERACTIVE_UNLOCK_LOGON logon{};
            hr = InitKerbLogon(
                credential.domain.data(),
                credential.username.data(),
                protectedPassword, scenario_, &logon);
            if (SUCCEEDED(hr)) {
                hr = PackKerbLogon(
                    logon, &serialization->rgbSerialization,
                    &serialization->cbSerialization);
            }
            if (SUCCEEDED(hr)) {
                hr = RetrieveNegotiatePackage(
                    &serialization->ulAuthenticationPackage);
            }
            if (SUCCEEDED(hr)) {
                serialization->clsidCredentialProvider =
                    CLSID_AkshCredentialProvider;
                *response = CPGSR_RETURN_CREDENTIAL_FINISHED;
            }
            SecureZeroMemory(
                protectedPassword,
                wcslen(protectedPassword) * sizeof(wchar_t));
            CoTaskMemFree(protectedPassword);
        }
        if (FAILED(hr)) {
            SHStrDupW(
                L"Aksh could not prepare the Windows credential.",
                statusText);
            *statusIcon = CPSI_ERROR;
        }
        return hr;
    }

    IFACEMETHODIMP ReportResult(
        NTSTATUS status, NTSTATUS, PWSTR* text,
        CREDENTIAL_PROVIDER_STATUS_ICON* icon) override {
        *text = nullptr;
        *icon = CPSI_NONE;
        if (status != STATUS_SUCCESS) {
            SHStrDupW(
                L"Windows rejected the stored credential. Run Aksh setup again.",
                text);
            *icon = CPSI_ERROR;
        }
        return S_OK;
    }

private:
    ~AkshCredential() {
        if (events_) events_->Release();
        --g_dllRefs;
    }

    std::atomic<long> refs_;
    CREDENTIAL_PROVIDER_USAGE_SCENARIO scenario_;
    ICredentialProviderCredentialEvents* events_;
};

class AkshProvider final : public ICredentialProvider {
public:
    AkshProvider()
        : refs_(1), scenario_(CPUS_INVALID), credential_(nullptr),
          events_(nullptr), adviseContext_(0), stopEvent_(nullptr),
          watcher_(nullptr) {
        InitializeCriticalSection(&guard_);
        ++g_dllRefs;
    }

    IFACEMETHODIMP QueryInterface(
        REFIID riid, void** object) override {
        if (!object) return E_INVALIDARG;
        *object = nullptr;
        if (IsEqualIID(riid, IID_IUnknown)
            || IsEqualIID(riid, IID_ICredentialProvider)) {
            *object = static_cast<ICredentialProvider*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    IFACEMETHODIMP_(ULONG) AddRef() override {
        return ++refs_;
    }

    IFACEMETHODIMP_(ULONG) Release() override {
        long value = --refs_;
        if (!value) delete this;
        return value;
    }

    IFACEMETHODIMP SetUsageScenario(
        CREDENTIAL_PROVIDER_USAGE_SCENARIO scenario,
        DWORD) override {
        if (scenario != CPUS_LOGON
            && scenario != CPUS_UNLOCK_WORKSTATION) {
            return E_NOTIMPL;
        }
        scenario_ = scenario;
        if (credential_) credential_->Release();
        credential_ =
            new (std::nothrow) AkshCredential(scenario);
        return credential_ ? S_OK : E_OUTOFMEMORY;
    }

    IFACEMETHODIMP SetSerialization(
        const CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION*)
        override {
        return E_NOTIMPL;
    }

    IFACEMETHODIMP Advise(
        ICredentialProviderEvents* events,
        UINT_PTR context) override {
        EnterCriticalSection(&guard_);
        if (events_) events_->Release();
        events_ = events;
        if (events_) events_->AddRef();
        adviseContext_ = context;
        LeaveCriticalSection(&guard_);
        stopEvent_ = CreateEventW(
            nullptr, TRUE, FALSE, nullptr);
        watcher_ = CreateThread(
            nullptr, 0, WatcherEntry, this, 0, nullptr);
        return watcher_
            ? S_OK : HRESULT_FROM_WIN32(GetLastError());
    }

    IFACEMETHODIMP UnAdvise() override {
        if (stopEvent_) SetEvent(stopEvent_);
        if (watcher_) {
            WaitForSingleObject(watcher_, 3000);
            CloseHandle(watcher_);
            watcher_ = nullptr;
        }
        if (stopEvent_) {
            CloseHandle(stopEvent_);
            stopEvent_ = nullptr;
        }
        EnterCriticalSection(&guard_);
        if (events_) events_->Release();
        events_ = nullptr;
        LeaveCriticalSection(&guard_);
        return S_OK;
    }

    IFACEMETHODIMP GetFieldDescriptorCount(
        DWORD* count) override {
        *count = FI_COUNT;
        return S_OK;
    }

    IFACEMETHODIMP GetFieldDescriptorAt(
        DWORD index,
        CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR** descriptor)
        override {
        return index < FI_COUNT
            ? CopyFieldDescriptor(kFields[index], descriptor)
            : E_INVALIDARG;
    }

    IFACEMETHODIMP GetCredentialCount(
        DWORD* count, DWORD* defaultIndex,
        BOOL* autoLogon) override {
        *count = credential_ ? 1 : 0;
        *defaultIndex =
            credential_ ? 0 : CREDENTIAL_PROVIDER_NO_DEFAULT;
        *autoLogon =
            credential_ && g_ready.load() ? TRUE : FALSE;
        return S_OK;
    }

    IFACEMETHODIMP GetCredentialAt(
        DWORD index,
        ICredentialProviderCredential** credential) override {
        if (index != 0 || !credential_) return E_INVALIDARG;
        *credential = credential_;
        credential_->AddRef();
        return S_OK;
    }

private:
    ~AkshProvider() {
        UnAdvise();
        if (credential_) credential_->Release();
        DeleteCriticalSection(&guard_);
        --g_dllRefs;
    }

    static DWORD WINAPI WatcherEntry(void* context) {
        return static_cast<AkshProvider*>(context)->Watch();
    }

    DWORD Watch() {
        HANDLE readyEvent =
            CreateEventW(nullptr, FALSE, FALSE, kReadyEvent);
        if (!readyEvent) return GetLastError();
        HANDLE handles[2] = {stopEvent_, readyEvent};
        while (WaitForMultipleObjects(
                   2, handles, FALSE, INFINITE)
               == WAIT_OBJECT_0 + 1) {
            g_ready.store(true);
            ICredentialProviderEvents* callback = nullptr;
            UINT_PTR context = 0;
            EnterCriticalSection(&guard_);
            callback = events_;
            context = adviseContext_;
            if (callback) callback->AddRef();
            LeaveCriticalSection(&guard_);
            if (callback) {
                callback->CredentialsChanged(context);
                callback->Release();
            }
        }
        CloseHandle(readyEvent);
        return 0;
    }

    std::atomic<long> refs_;
    CREDENTIAL_PROVIDER_USAGE_SCENARIO scenario_;
    AkshCredential* credential_;
    ICredentialProviderEvents* events_;
    UINT_PTR adviseContext_;
    HANDLE stopEvent_;
    HANDLE watcher_;
    CRITICAL_SECTION guard_;
};

class AkshClassFactory final : public IClassFactory {
public:
    AkshClassFactory() : refs_(1) {
        ++g_dllRefs;
    }

    IFACEMETHODIMP QueryInterface(
        REFIID riid, void** object) override {
        if (!object) return E_INVALIDARG;
        *object = nullptr;
        if (IsEqualIID(riid, IID_IUnknown)
            || IsEqualIID(riid, IID_IClassFactory)) {
            *object = static_cast<IClassFactory*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    IFACEMETHODIMP_(ULONG) AddRef() override {
        return ++refs_;
    }

    IFACEMETHODIMP_(ULONG) Release() override {
        long value = --refs_;
        if (!value) delete this;
        return value;
    }

    IFACEMETHODIMP CreateInstance(
        IUnknown* outer, REFIID riid, void** object) override {
        if (outer) return CLASS_E_NOAGGREGATION;
        auto provider = new (std::nothrow) AkshProvider();
        if (!provider) return E_OUTOFMEMORY;
        HRESULT hr = provider->QueryInterface(riid, object);
        provider->Release();
        return hr;
    }

    IFACEMETHODIMP LockServer(BOOL lock) override {
        if (lock) {
            ++g_dllRefs;
        } else {
            --g_dllRefs;
        }
        return S_OK;
    }

private:
    ~AkshClassFactory() {
        --g_dllRefs;
    }

    std::atomic<long> refs_;
};

extern "C" HRESULT __stdcall DllCanUnloadNow() {
    return g_dllRefs.load() == 0 ? S_OK : S_FALSE;
}

extern "C" HRESULT __stdcall DllGetClassObject(
    REFCLSID clsid, REFIID riid, void** object) {
    if (!IsEqualCLSID(clsid, CLSID_AkshCredentialProvider)) {
        return CLASS_E_CLASSNOTAVAILABLE;
    }
    auto factory = new (std::nothrow) AkshClassFactory();
    if (!factory) return E_OUTOFMEMORY;
    HRESULT hr = factory->QueryInterface(riid, object);
    factory->Release();
    return hr;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
