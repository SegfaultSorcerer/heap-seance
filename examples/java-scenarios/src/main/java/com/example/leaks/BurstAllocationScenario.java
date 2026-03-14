package com.example.leaks;

import java.util.ArrayList;
import java.util.List;

public final class BurstAllocationScenario {
    private BurstAllocationScenario() {
    }

    public static void main(String[] args) throws Exception {
        System.out.println("BurstAllocationScenario started");
        int cycle = 0;
        while (true) {
            List<byte[]> burst = new ArrayList<>();
            for (int i = 0; i < 600; i++) {
                burst.add(new byte[32 * 1024]);
            }
            cycle++;
            if (cycle % 5 == 0) {
                System.out.printf("cycle=%d temporary_objects=%d%n", cycle, burst.size());
            }
            burst.clear();
            Thread.sleep(450);
        }
    }
}
