/// Trading Vault Module for Aptos Alpha Bot
/// Manages user deposits, withdrawals, and profit sharing
module aptos_alpha_bot::trading_vault {
    use std::signer;
    use std::vector;
    use std::error;
    use std::option::{Self, Option};
    use aptos_framework::coin;
    use aptos_framework::aptos_coin::AptosCoin;
    use aptos_framework::timestamp;
    use aptos_framework::event::{Self, EventHandle};
    use aptos_framework::account;

    /// Error codes
    const E_NOT_AUTHORIZED: u64 = 1;
    const E_INSUFFICIENT_BALANCE: u64 = 2;
    const E_VAULT_NOT_FOUND: u64 = 3;
    const E_MINIMUM_DEPOSIT_NOT_MET: u64 = 4;
    const E_WITHDRAWAL_LOCKED: u64 = 5;

    /// Minimum deposit amount (1 APT = 100000000 octas)
    const MINIMUM_DEPOSIT: u64 = 50000000; // 0.5 APT

    /// Performance fee (10% = 1000 basis points)
    const PERFORMANCE_FEE_BPS: u64 = 1000;

    /// Lockup period in seconds (1 day = 86400 seconds)
    const LOCKUP_PERIOD: u64 = 86400;

    /// User deposit information
    struct UserDeposit has store, drop {
        amount: u64,
        deposit_time: u64,
        last_profit_share: u64,
    }

    /// Trading vault resource
    struct TradingVault has key {
        /// Total vault balance
        total_balance: u64,
        /// User deposits mapping (user_address -> UserDeposit)
        user_deposits: vector<UserDeposit>,
        user_addresses: vector<address>,
        /// Performance metrics
        total_profit: u64,
        total_trades: u64,
        /// Vault settings
        minimum_deposit: u64,
        performance_fee_bps: u64,
        lockup_period: u64,
        /// Events
        deposit_events: EventHandle<DepositEvent>,
        withdrawal_events: EventHandle<WithdrawalEvent>,
        trade_events: EventHandle<TradeEvent>,
    }

    /// Events
    struct DepositEvent has drop, store {
        user: address,
        amount: u64,
        timestamp: u64,
    }

    struct WithdrawalEvent has drop, store {
        user: address,
        amount: u64,
        timestamp: u64,
    }

    struct TradeEvent has drop, store {
        trader: address,
        symbol: vector<u8>,
        side: vector<u8>,
        amount: u64,
        price: u64,
        profit_loss: u64,
        timestamp: u64,
    }

    /// Initialize the trading vault
    public entry fun initialize_vault(admin: &signer) {
        let admin_addr = signer::address_of(admin);
        
        assert!(!exists<TradingVault>(admin_addr), error::already_exists(E_VAULT_NOT_FOUND));
        
        let vault = TradingVault {
            total_balance: 0,
            user_deposits: vector::empty<UserDeposit>(),
            user_addresses: vector::empty<address>(),
            total_profit: 0,
            total_trades: 0,
            minimum_deposit: MINIMUM_DEPOSIT,
            performance_fee_bps: PERFORMANCE_FEE_BPS,
            lockup_period: LOCKUP_PERIOD,
            deposit_events: account::new_event_handle<DepositEvent>(admin),
            withdrawal_events: account::new_event_handle<WithdrawalEvent>(admin),
            trade_events: account::new_event_handle<TradeEvent>(admin),
        };
        
        move_to(admin, vault);
    }

    /// Deposit APT into the trading vault
    public entry fun deposit(
        user: &signer,
        vault_owner: address,
        amount: u64
    ) acquires TradingVault {
        let user_addr = signer::address_of(user);
        
        assert!(exists<TradingVault>(vault_owner), error::not_found(E_VAULT_NOT_FOUND));
        assert!(amount >= MINIMUM_DEPOSIT, error::invalid_argument(E_MINIMUM_DEPOSIT_NOT_MET));
        
        let vault = borrow_global_mut<TradingVault>(vault_owner);
        
        // Transfer APT from user to vault
        let deposit_coin = coin::withdraw<AptosCoin>(user, amount);
        coin::deposit(vault_owner, deposit_coin);
        
        // Update user deposit record
        let current_time = timestamp::now_seconds();
        let user_deposit = UserDeposit {
            amount,
            deposit_time: current_time,
            last_profit_share: 0,
        };
        
        // Find existing user or add new one
        let user_index_opt = find_user_index(&vault.user_addresses, user_addr);
        if (option::is_some(&user_index_opt)) {
            let index = option::extract(&mut user_index_opt);
            let existing_deposit = vector::borrow_mut(&mut vault.user_deposits, index);
            existing_deposit.amount = existing_deposit.amount + amount;
        } else {
            vector::push_back(&mut vault.user_addresses, user_addr);
            vector::push_back(&mut vault.user_deposits, user_deposit);
        };
        
        vault.total_balance = vault.total_balance + amount;
        
        // Emit deposit event
        event::emit_event(&mut vault.deposit_events, DepositEvent {
            user: user_addr,
            amount,
            timestamp: current_time,
        });
    }

    /// Withdraw APT from the trading vault
    public entry fun withdraw(
        user: &signer,
        vault_owner: address,
        amount: u64
    ) acquires TradingVault {
        let user_addr = signer::address_of(user);
        
        assert!(exists<TradingVault>(vault_owner), error::not_found(E_VAULT_NOT_FOUND));
        
        let vault = borrow_global_mut<TradingVault>(vault_owner);
        
        // Find user deposit
        let user_index_opt = find_user_index(&vault.user_addresses, user_addr);
        assert!(option::is_some(&user_index_opt), error::not_found(E_INSUFFICIENT_BALANCE));
        
        let index = option::extract(&mut user_index_opt);
        let user_deposit = vector::borrow_mut(&mut vault.user_deposits, index);
        
        // Check lockup period
        let current_time = timestamp::now_seconds();
        assert!(
            current_time >= user_deposit.deposit_time + vault.lockup_period,
            error::permission_denied(E_WITHDRAWAL_LOCKED)
        );
        
        assert!(user_deposit.amount >= amount, error::invalid_argument(E_INSUFFICIENT_BALANCE));
        
        // Update user deposit
        user_deposit.amount = user_deposit.amount - amount;
        vault.total_balance = vault.total_balance - amount;
        
        // Note: In production, this would transfer APT back to user
        // For now, we'll just update the balance (simplified for demo)
        // let withdrawal_coin = coin::withdraw<AptosCoin>(vault_signer, amount);
        // coin::deposit(user_addr, withdrawal_coin);
        
        // Emit withdrawal event
        event::emit_event(&mut vault.withdrawal_events, WithdrawalEvent {
            user: user_addr,
            amount,
            timestamp: current_time,
        });
    }

    /// Record a trade execution
    public entry fun record_trade(
        trader: &signer,
        vault_owner: address,
        symbol: vector<u8>,
        side: vector<u8>,
        amount: u64,
        price: u64,
        profit_loss: u64,
    ) acquires TradingVault {
        let trader_addr = signer::address_of(trader);
        
        assert!(exists<TradingVault>(vault_owner), error::not_found(E_VAULT_NOT_FOUND));
        assert!(trader_addr == vault_owner, error::permission_denied(E_NOT_AUTHORIZED));
        
        let vault = borrow_global_mut<TradingVault>(vault_owner);
        
        vault.total_trades = vault.total_trades + 1;
        vault.total_profit = vault.total_profit + profit_loss;
        
        // Emit trade event
        event::emit_event(&mut vault.trade_events, TradeEvent {
            trader: trader_addr,
            symbol,
            side,
            amount,
            price,
            profit_loss,
            timestamp: timestamp::now_seconds(),
        });
    }

    /// Get vault statistics
    public fun get_vault_stats(vault_owner: address): (u64, u64, u64, u64) acquires TradingVault {
        assert!(exists<TradingVault>(vault_owner), error::not_found(E_VAULT_NOT_FOUND));
        
        let vault = borrow_global<TradingVault>(vault_owner);
        (vault.total_balance, vault.total_profit, vault.total_trades, vector::length(&vault.user_addresses))
    }

    /// Get user deposit amount
    public fun get_user_deposit(vault_owner: address, user_addr: address): u64 acquires TradingVault {
        assert!(exists<TradingVault>(vault_owner), error::not_found(E_VAULT_NOT_FOUND));
        
        let vault = borrow_global<TradingVault>(vault_owner);
        let user_index_opt = find_user_index(&vault.user_addresses, user_addr);
        
        if (option::is_some(&user_index_opt)) {
            let index = option::extract(&mut user_index_opt);
            let user_deposit = vector::borrow(&vault.user_deposits, index);
            user_deposit.amount
        } else {
            0
        }
    }

    /// Helper function to find user index
    fun find_user_index(addresses: &vector<address>, target: address): Option<u64> {
        let len = vector::length(addresses);
        let i = 0;
        
        while (i < len) {
            if (*vector::borrow(addresses, i) == target) {
                return option::some(i)
            };
            i = i + 1;
        };
        
        option::none<u64>()
    }

    #[test_only]
    use aptos_framework::account::create_account_for_test;

    #[test(admin = @aptos_alpha_bot, user = @0x123)]
    public entry fun test_vault_operations(admin: signer, user: signer) acquires TradingVault {
        let admin_addr = signer::address_of(&admin);
        let user_addr = signer::address_of(&user);
        
        // Create accounts for testing
        create_account_for_test(admin_addr);
        create_account_for_test(user_addr);
        
        // Initialize vault
        initialize_vault(&admin);
        
        // Test deposit
        coin::register<AptosCoin>(&user);
        coin::register<AptosCoin>(&admin);
        
        // Note: In production tests, you would fund the account properly
        // For compilation, we'll skip the actual funding
        
        // Test deposit
        deposit(&user, admin_addr, 50000000);
        
        // Verify deposit
        let user_balance = get_user_deposit(admin_addr, user_addr);
        assert!(user_balance == 50000000, 1);
        
        let (total_balance, _, _, user_count) = get_vault_stats(admin_addr);
        assert!(total_balance == 50000000, 2);
        assert!(user_count == 1, 3);
    }
}
