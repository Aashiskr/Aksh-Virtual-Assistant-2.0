package com.aksh.remote;

import java.net.URI;

final class UrlPolicy {
    private UrlPolicy() {
    }

    static boolean isAllowedSecureUrl(String value) {
        if (value == null || value.isBlank()) {
            return true;
        }
        try {
            URI uri = URI.create(value);
            if (uri.getUserInfo() != null || uri.getHost() == null) {
                return false;
            }
            return "https".equalsIgnoreCase(uri.getScheme());
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }
}
