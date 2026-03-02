/**
 * Tests for the ChatInput component.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '../components/chat/ChatInput';

describe('ChatInput', () => {
  const defaultProps = {
    onSubmit: vi.fn(),
    isLoading: false,
  };

  it('renders the textarea with correct placeholder', () => {
    render(<ChatInput {...defaultProps} />);
    expect(
      screen.getByPlaceholderText(/Ask about a competitor/i)
    ).toBeInTheDocument();
  });

  it('renders the submit button as disabled when input is empty', () => {
    render(<ChatInput {...defaultProps} />);
    const button = screen.getByRole('button', { name: /submit digest request/i });
    expect(button).toBeDisabled();
  });

  it('enables the submit button when text is entered', async () => {
    render(<ChatInput {...defaultProps} />);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    await userEvent.type(textarea, 'Walmart Connect digest');
    const button = screen.getByRole('button', { name: /submit digest request/i });
    expect(button).toBeEnabled();
  });

  it('calls onSubmit with trimmed text when button is clicked', async () => {
    const onSubmit = vi.fn();
    render(<ChatInput {...defaultProps} onSubmit={onSubmit} />);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    await userEvent.type(textarea, '  Walmart Connect  ');
    const button = screen.getByRole('button', { name: /submit digest request/i });
    await userEvent.click(button);
    expect(onSubmit).toHaveBeenCalledWith('Walmart Connect');
  });

  it('clears the input after successful submission', async () => {
    render(<ChatInput {...defaultProps} />);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    await userEvent.type(textarea, 'test prompt');
    const button = screen.getByRole('button', { name: /submit digest request/i });
    await userEvent.click(button);
    expect(textarea).toHaveValue('');
  });

  it('shows "Generating..." text when isLoading is true', () => {
    render(<ChatInput {...defaultProps} isLoading={true} />);
    expect(screen.getByText(/generating/i)).toBeInTheDocument();
  });

  it('disables the textarea and button when isLoading is true', () => {
    render(<ChatInput {...defaultProps} isLoading={true} />);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    expect(textarea).toBeDisabled();
  });

  it('fills in a suggestion when suggestion chip is clicked', async () => {
    render(<ChatInput {...defaultProps} />);
    const suggestionButton = screen.getByRole('button', {
      name: /daily digest for walmart connect/i,
    });
    await userEvent.click(suggestionButton);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    expect(textarea).toHaveValue('Daily digest for Walmart Connect');
  });

  it('calls onSubmit on Ctrl+Enter keyboard shortcut', async () => {
    const onSubmit = vi.fn();
    render(<ChatInput {...defaultProps} onSubmit={onSubmit} />);
    const textarea = screen.getByRole('textbox', { name: /digest prompt/i });
    await userEvent.type(textarea, 'test prompt');
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    expect(onSubmit).toHaveBeenCalledWith('test prompt');
  });

  it('renders the prompt suggestions group', () => {
    render(<ChatInput {...defaultProps} />);
    const group = screen.getByRole('group', { name: /prompt suggestions/i });
    expect(group).toBeInTheDocument();
  });
});
